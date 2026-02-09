"""Video to Markdown converter using frame extraction and OCR."""

from difflib import SequenceMatcher
from pathlib import Path

from fileconverter.converters.base import BaseConverter, ConversionResult


def _format_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_timestamp_filename(seconds: float) -> str:
    """Format seconds as HHhMMmSSs for safe filenames."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}h{minutes:02d}m{secs:02d}s"


class VideoConverter(BaseConverter):
    """Convert video files to Markdown by extracting key frames and running OCR."""

    DEFAULT_FRAME_INTERVAL_SEC = 5.0
    SIMILARITY_THRESHOLD = 0.95

    def __init__(
        self, extract_images: bool = False, frame_interval: float | None = None
    ):
        super().__init__(extract_images=extract_images)
        self.frame_interval = frame_interval or self.DEFAULT_FRAME_INTERVAL_SEC

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv"]

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a video file to Markdown via frame extraction and OCR.

        Args:
            file_path: Path to the video file.

        Returns:
            ConversionResult with the conversion outcome.
        """
        try:
            import cv2
        except ImportError:
            return self._create_error_result(
                file_path,
                "opencv-python is not installed. Run: pip install opencv-python",
            )

        try:
            import pytesseract
        except ImportError:
            return self._create_error_result(
                file_path,
                "pytesseract is not installed. Run: pip install pytesseract",
            )

        try:
            from PIL import Image
        except ImportError:
            return self._create_error_result(
                file_path,
                "Pillow is not installed. Run: pip install Pillow",
            )

        try:
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                return self._create_error_result(
                    file_path, f"Failed to open video: {file_path.name}"
                )
        except Exception as e:
            return self._create_error_result(
                file_path, f"Failed to open video: {e}"
            )

        try:
            # Gather video metadata
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration_sec = frame_count / fps if fps > 0 else 0

            # Calculate frame extraction interval in frame numbers
            frame_interval_frames = max(1, int(fps * self.frame_interval))

            # Extract frames at intervals and run OCR
            frames_data: list[tuple[float, str, Path | None]] = []
            prev_text: str | None = None
            frame_idx = 0
            extracted_images: list[Path] = []

            output_dir = None
            if self.extract_images:
                output_dir = file_path.parent / f"{file_path.stem}_frames"
                output_dir.mkdir(exist_ok=True)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_interval_frames == 0:
                    timestamp_sec = frame_idx / fps if fps > 0 else 0

                    # Convert BGR (cv2) to RGB (PIL)
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_frame)

                    # Run OCR
                    try:
                        ocr_text = pytesseract.image_to_string(pil_image).strip()
                    except pytesseract.TesseractNotFoundError:
                        pil_image.close()
                        return self._create_error_result(
                            file_path,
                            "Tesseract OCR engine is not installed. "
                            "Install it from https://github.com/tesseract-ocr/tesseract "
                            "and ensure it is on your PATH.",
                        )

                    # Deduplicate: skip if text is same as previous frame
                    if ocr_text and self._is_duplicate_text(prev_text, ocr_text):
                        pil_image.close()
                        frame_idx += 1
                        continue

                    # Save frame image if extract_images
                    frame_path = None
                    if self.extract_images and output_dir is not None:
                        frame_filename = (
                            f"frame_{frame_idx:06d}"
                            f"_{_format_timestamp_filename(timestamp_sec)}.png"
                        )
                        frame_path = output_dir / frame_filename
                        pil_image.save(frame_path, format="PNG")
                        extracted_images.append(frame_path)

                    frames_data.append((timestamp_sec, ocr_text, frame_path))
                    if ocr_text:
                        prev_text = ocr_text

                    pil_image.close()

                frame_idx += 1

            # Build Markdown
            lines = [
                f"# Video: {file_path.name}",
                "",
                (
                    f"**Duration:** {_format_duration(duration_sec)} | "
                    f"**Resolution:** {width}x{height} | "
                    f"**FPS:** {fps:.1f} | "
                    f"**Frames Analyzed:** {len(frames_data)}"
                ),
                "",
            ]

            if not frames_data:
                lines.append("*No frames could be extracted from this video.*")
            else:
                has_any_text = any(text for _, text, _ in frames_data)
                if not has_any_text:
                    lines.append("*No text detected in any extracted frame.*")
                else:
                    lines.append("## Extracted Text by Timestamp")
                    lines.append("")
                    for timestamp_sec, ocr_text, frame_path in frames_data:
                        ts_str = _format_duration(timestamp_sec)
                        lines.append(f"### [{ts_str}]")
                        lines.append("")
                        if ocr_text:
                            lines.append(ocr_text)
                        else:
                            lines.append("*No text detected.*")
                        lines.append("")
                        if frame_path is not None:
                            lines.append(f"![Frame at {ts_str}]({frame_path.name})")
                            lines.append("")

            markdown = "\n".join(lines)
            return self._create_success_result(file_path, markdown, extracted_images)

        except Exception as e:
            return self._create_error_result(
                file_path, f"Failed to convert video: {e}"
            )
        finally:
            cap.release()

    def _is_duplicate_text(self, prev_text: str | None, current_text: str) -> bool:
        """Check if current OCR text is essentially the same as previous."""
        if prev_text is None:
            return False

        norm_prev = " ".join(prev_text.split())
        norm_curr = " ".join(current_text.split())

        if norm_prev == norm_curr:
            return True

        ratio = SequenceMatcher(None, norm_prev, norm_curr).ratio()
        return ratio >= self.SIMILARITY_THRESHOLD
