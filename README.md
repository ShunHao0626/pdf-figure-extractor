# PDF Figure Extractor

**English** · [简体中文](README_CN.md)

A Python tool for extracting figures and charts from PDF documents using page-structure JSON and normalized bounding-box coordinates. Each extracted image is saved with its associated caption, footnote, and structured metadata.

## Features

- Renders PDF pages as images with PyMuPDF.
- Reads predefined `group`, `image`, `figuregroup`, and `chart` hierarchies from JSON.
- Crops figures using normalized `bbox` coordinates.
- Distinguishes individual panels from complete images to avoid duplicate extraction.
- Associates captions and footnotes with their corresponding figures.
- Generates readable filenames from panel identifiers and descriptions.
- Creates a metadata JSON file for every extracted image.
- Produces an `extraction_index.json` file containing all extraction records.
- Skips regions that are too small or produce empty crops.

## Workflow

```text
PDF + page-structure JSON
          |
          v
Render each page as a PIL image
          |
          v
Traverse the JSON and collect target elements
          |
          v
Convert normalized bounding boxes to pixel coordinates
          |
          v
Crop and save each target as a PNG
          |
          v
Write per-image metadata and a combined index
```

## Project Structure

```text
pdf-figure-extractor/
├── extract_sources.py          # Main extraction script
├── examples/                   # Output-format example (see examples/README.md)
└── README.md
```

The script uses two input files:

- `PDF_PATH`: the PDF document from which figures will be extracted.
- `JSON_PATH`: the page-structure JSON containing element types, coordinates, captions, and footnotes.

## Requirements

- Python 3.9 or later
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- [Pillow](https://pillow.readthedocs.io/)

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PyMuPDF Pillow
```

## Configuration

Before running the script, configure the working directory and input paths near the top of `extract_sources.py`:

```python
WORK_DIR = Path(__file__).resolve().parent
PDF_PATH = WORK_DIR / "input.pdf"
JSON_PATH = WORK_DIR / "connected-imagecaption.json"
OUT_DIR = WORK_DIR / "output"
```

The rendering resolution is controlled by:

```python
RENDER_DPI = 150
```

A higher DPI produces larger and sharper images but increases memory usage and processing time.

To customize output filenames, update the panel maps and table information:

```python
FIG1_ORDER_MAP = {...}
FIG2_LEGEND_MAP = {...}
FIG3_ORDER_MAP = {...}
TABLE_INFO = (...)
```

Each mapping entry uses the following format:

```python
json_order: ("panel_id", "description")
```

Example:

```python
5: ("A", "performance_curve")
```

## Usage

Run the extractor from the project directory:

```bash
python extract_sources.py
```

The script reports:

- The PDF, JSON, and output paths.
- The number of PDF and JSON pages.
- The number of extraction targets found.
- The filename and associated text for each saved image.
- The final number of images written.

## Extraction Rules

- A `chart` element is extracted as an individual panel.
- An `image` element is extracted only when it does not contain a `figuregroup`.
- A `figuregroup` acts as a panel container and is not exported directly.
- A `group` associates images with captions and footnotes and is not exported directly.
- Elements without a `bbox` are ignored.
- Elements with a normalized width or height below `0.005` are ignored.
- Coordinates outside the page are clamped to valid image boundaries.
- Empty crop results are skipped.

## Output Files

When a panel identifier and description are available, the image filename follows this format:

```text
{panel_id}_{description}.png
```

The corresponding metadata file is named:

```text
{panel_id}_{description}_meta.json
```

If no panel identifier is configured, the script creates a fallback filename from the figure number, page number, element order, and element type.

The output directory also contains:

```text
extraction_index.json
```

This file is a JSON array containing the metadata for every extracted image, making it suitable for batch processing and downstream analysis.

## Metadata Fields

| Field | Description |
|---|---|
| `page` | One-based PDF page number |
| `order` | Nested element order from the source JSON |
| `type` | Target type, such as `chart` or `image` |
| `panel_id` | Panel or table identifier |
| `description` | Short description used in the filename |
| `figure_label` | Associated figure or table title |
| `bbox_norm` | Normalized `x1`, `y1`, `x2`, and `y2` crop coordinates |
| `caption` | Associated caption text |
| `footnote` | Combined caption and footnote text in the current implementation |
| `context` | Combined footnote text in the current implementation |
| `image_size_px` | Output image dimensions as `[width, height]` |
| `pdf_size` | Page dimensions recorded in the source JSON |

> In the current implementation, the assignment order of values returned by `build_text()` means that `footnote` and `context` do not follow their conventional meanings exactly. If these fields must be strictly separated, update their assignment in `collect_targets()`.

## Core Functions

### `sanitize_filename()`

Removes invalid filename characters, collapses repeated underscores, and limits filename length.

### `render_pdf_to_images()`

Renders every PDF page at the configured DPI and converts it to an RGB PIL image.

### `crop_subimage()`

Converts normalized coordinates into pixel coordinates, clamps them to valid boundaries, and crops the source image.

### `collect_targets()`

Traverses the JSON structure for one page, associates captions and footnotes, and collects all eligible extraction targets.

### `main()`

Validates the inputs, loads the JSON, renders the PDF, collects targets, saves images and metadata, and writes the combined index.

## Limitations

- Input and output paths are configured in the source code; command-line arguments are not currently supported.
- Panel identifiers and descriptions depend on manually maintained mapping tables.
- The mappings must be updated if page numbers or JSON element order values change.
- Standalone `image` elements currently share one `TABLE_INFO` value. The naming logic must be extended when processing multiple independent images.
- Existing files with the same names are overwritten, while obsolete files are not removed automatically.
- OCR and upstream parsing errors are preserved in the exported metadata.
