# FileConverter

CLI tool to convert PDF, HTML, DOCX, XLSX, MSG (Outlook email), CSV, PPTX (PowerPoint), image, video files, and web pages (URLs) to Markdown for use as LLM input.

## Installation

```bash
pip install -e .
```

## Usage

### Single file conversion

```bash
fileconverter convert document.pdf
fileconverter convert report.docx
fileconverter convert data.xlsx
fileconverter convert page.html
fileconverter convert email.msg
fileconverter convert data.csv
fileconverter convert presentation.pptx
fileconverter convert photo.png
fileconverter convert scan.jpg
fileconverter convert meeting.mp4
fileconverter convert https://example.com/article
```

### Multiple files

```bash
fileconverter convert doc1.pdf doc2.docx spreadsheet.xlsx
```

### Directory conversion

```bash
# Non-recursive (current directory only)
fileconverter convert ./documents/

# Recursive
fileconverter convert ./documents/ -r

# With custom output directory
fileconverter convert ./documents/ -r -o ./markdown/
```

### Format filtering

```bash
# Only PDFs
fileconverter convert ./input/ --format pdf -r

# PDFs and DOCX files
fileconverter convert ./input/ --format pdf --format docx -r
```

### Merge mode

Combine all converted files into a single Markdown document, ready to paste into an LLM context window.

```bash
# Merge multiple files into merged.md
fileconverter convert doc1.pdf doc2.docx --merge -o ./output/

# Merge a folder recursively with a custom filename
fileconverter convert ./docs/ -r --merge --merge-filename context.md -o ./output/

# Dry run to preview what would be merged
fileconverter convert ./docs/ -r --merge --dry-run
```

The merged output uses `# filename` headers and `---` separators between documents:

```markdown
# file1.pdf

<converted content>

---

# file2.docx

<converted content>
```

Individual `.md` files are **not** written in merge mode — only the single merged file is produced. Failed conversions are skipped in the output but still reported as errors.

### URL / web page conversion

```bash
# Convert a web page to Markdown
fileconverter convert https://example.com/article

# Save to a specific directory
fileconverter convert https://blog.example.com/post-123 -o ./output/

# Mix files and URLs, merged into a single document
fileconverter convert document.pdf https://example.com/page --merge -o ./output/
```

Web pages are fetched, boilerplate (navigation, sidebars, footers) is stripped using Mozilla's Readability algorithm, and the main content is converted to clean Markdown.

### Additional options

```bash
# Dry run (show what would be converted)
fileconverter convert ./documents/ -r --dry-run

# Extract images from documents
fileconverter convert document.pdf --extract-images

# Control parallel workers
fileconverter convert ./documents/ -r -w 8
```

## Supported Formats

- **PDF** - Converted using pymupdf4llm with table post-processing
  - Degenerate tables (e.g., flowcharts misread as wide tables) are automatically detected and restructured into readable headings and bullet lists
  - Normal tables are cleaned up: `<br>` tags replaced, generic headers inferred, redundant sub-header rows removed
- **HTML/HTM** - Converted using markdownify + BeautifulSoup
- **DOCX** - Converted using mammoth + markdownify
- **XLSX** - Converted using openpyxl (native markdown table generation)
- **MSG** - Outlook email messages with full metadata (subject, from, to, date) and attachments
  - Use `--extract-images` to save attachments and embed images in the markdown
  - Converts HTML email bodies to clean markdown
  - Preserves email structure and metadata
- **CSV** - Tabular data converted to clean markdown tables
  - Auto-detects delimiters and encoding
  - Handles headers and proper column alignment
  - Perfect for data analysis and reporting
- **PPTX** - PowerPoint presentations with full slide structure
  - Extracts slide content, titles, and text
  - Converts tables and bullet points
  - Use `--extract-images` to save slide images
  - Includes speaker notes if present
- **Images** (PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP) - OCR text extraction using Tesseract
  - Extracts text from photos, screenshots, and scanned documents
  - Includes image metadata (format, dimensions, color mode)
  - Use `--extract-images` to copy the original image alongside the markdown
  - Requires [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on the system
- **Video** (MP4, AVI, MKV, MOV, WEBM, WMV) - Frame extraction with OCR text recognition
  - Extracts key frames at configurable intervals (default 5 seconds)
  - Runs OCR on each frame and deduplicates text across consecutive frames
  - Includes video metadata (duration, resolution, FPS)
  - Requires [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and OpenCV
- **URL** (HTTP/HTTPS) - Web page fetching with content extraction
  - Fetches the page and extracts main content using Mozilla's Readability algorithm
  - Strips boilerplate (navigation, sidebars, footers, ads)
  - Converts extracted HTML to clean Markdown
  - Can be mixed with local files in batch and merge modes

## Quality Score

Each converted file is automatically scored for extraction quality (0–100%). The score appears in the output next to each file:

```
[OK 92%] report.pdf -> report.md
[OK 78%] scan.jpg -> scan.md
[OK 45%] garbled.pdf -> garbled.md
```

The score is a weighted average of format-agnostic heuristics:
- **Word density** (25%) — ratio of dictionary-like words to total tokens
- **Garbled text detection** (25%) — absence of garbled character patterns
- **Content length** (20%) — penalises very short output (likely failed extraction)
- **Whitespace ratio** (15%) — excessive blank lines suggest extraction issues
- **Markdown structure** (15%) — presence of headings, lists, tables, paragraphs

Score ranges: 90–100% excellent, 70–89% good, 50–69% fair, <50% poor. Files with low scores likely need manual review. The score is not shown during `--dry-run`.

## Output

By default, converted files are saved in the same directory as the source with a `.md` extension. Use `-o` to specify a different output directory.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
