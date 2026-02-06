# FileConverter

CLI tool to convert PDF, HTML, DOCX, XLSX, MSG (Outlook email), CSV, PPTX (PowerPoint), and image files to Markdown for use as Claude/LLM input.

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

- **PDF** - Converted using pymupdf4llm (excellent table and layout handling)
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

## Output

By default, converted files are saved in the same directory as the source with a `.md` extension. Use `-o` to specify a different output directory.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
