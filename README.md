# PDF Layout Detection Pipeline for Vietnamese Legal Documents

A production-ready pipeline for detecting document layout elements (header, title, article, paragraph, list, table, signature, footer) in Vietnamese legal documents sourced from [vbpl.vn](https://vbpl.vn).

## Overview

This project implements a **hybrid approach**:

| Strategy | When Used | Speed |
|---|---|---|
| **pdfplumber + heuristics** | PDF has a text layer | ⚡ Fast |
| **YOLOv8 inference** | Scanned PDF (no text) | 🐢 Slower, GPU recommended |
| **Active learning** | Improving model accuracy | 🔄 Iterative |

### Layout Classes (8)

| ID | Class | Description |
|----|-------|-------------|
| 0 | `header` | Document header (issuing authority, doc number) |
| 1 | `title` | Document title (QUYẾT ĐỊNH, NGHỊ ĐỊNH, …) |
| 2 | `article` | Article block starting with "Điều N" |
| 3 | `paragraph` | Standard body text |
| 4 | `list` | Bulleted or numbered items |
| 5 | `table` | Tabular data |
| 6 | `signature` | Signature area |
| 7 | `footer` | Page footer, recipient list |

---

## Project Structure

```
pdf_layout_project/
├── config/
│   └── config.yaml                 # All configurable settings
├── data/
│   ├── pdfs/                       # Downloaded PDF files
│   ├── metadata/                   # JSON metadata from API
│   ├── images/                     # Rendered PNG pages
│   ├── annotations/                # Soft labels from pdfplumber (JSON)
│   ├── yolo/                       # YOLO dataset (images + labels)
│   └── manual_annotations/         # Hand-corrected labels
├── scripts/
│   ├── 01_crawl_pdfs.py            # Crawl PDFs from vbpl.vn API
│   ├── 02_extract_layout_pdfplumber.py  # Extract text/bbox + heuristic labels
│   ├── 03_convert_to_yolo.py       # Convert to YOLO format
│   ├── 04_prepare_active_learning.py    # Select uncertain samples
│   ├── 05_train_yolo.py            # Fine-tune YOLOv8
│   ├── 06_predict_pdf.py           # Predict layout on new PDF
│   └── utils.py                    # Shared utilities
├── models/                         # Trained YOLO weights
├── metrics/                        # Training metrics CSV
├── requirements.txt
├── .gitignore
├── README.md
└── run_pipeline.py                 # Master orchestration script
```

---

## Installation

### Prerequisites

- **Python 3.10+**
- **Poppler** (required for `pdf2image` on Windows)
  - Download from [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
  - Extract and note the path to the `bin/` directory
  - Update `config/config.yaml` → `poppler.path`

### Setup

```powershell
# Clone or copy the project
cd pdf_layout_project

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Edit `config/config.yaml` to set:

- **`poppler.path`** — Path to your Poppler `bin/` directory (e.g., `C:/poppler/Library/bin`)
- **`api.max_documents`** — How many PDFs to download
- **`yolo.device`** — `"cpu"` or `"0"` for CUDA GPU
- **Classification thresholds** — Tune heuristic rules as needed

---

## Usage — Step by Step

### Step 1: Crawl PDFs

Download legal documents from the vbpl.vn API:

```powershell
python scripts/01_crawl_pdfs.py --max 200
```

- Downloads PDFs to `data/pdfs/`
- Saves metadata JSON to `data/metadata/`
- Automatically skips already-downloaded files (resumable)

### Step 2: Extract Layout with pdfplumber

Extract text, bounding boxes, and generate soft labels using heuristic rules:

```powershell
python scripts/02_extract_layout_pdfplumber.py
```

Or process a single PDF:

```powershell
python scripts/02_extract_layout_pdfplumber.py --pdf data/pdfs/12345.pdf
```

- Outputs annotations to `data/annotations/{id}.json`
- Renders page images to `data/images/{id}_page_{n}.png`

### Step 3: Convert to YOLO Format

Convert the soft labels into YOLO-format training data:

```powershell
python scripts/03_convert_to_yolo.py
```

Use a custom confidence threshold:

```powershell
python scripts/03_convert_to_yolo.py --min-confidence 0.8
```

- Creates `data/yolo/images/{train,val}/` and `data/yolo/labels/{train,val}/`
- Generates `data/yolo/data.yaml`

### Step 4: Train YOLOv8 (Optional for initial run)

Fine-tune YOLOv8n on the generated dataset:

```powershell
python scripts/05_train_yolo.py --epochs 50 --batch 16

# With GPU:
python scripts/05_train_yolo.py --epochs 100 --device 0

# Resume interrupted training:
python scripts/05_train_yolo.py --resume
```

- Best model saved to `models/best.pt`
- Metrics logged to `metrics/training_metrics.csv`

### Step 5: Active Learning

Select uncertain samples for manual annotation:

```powershell
python scripts/04_prepare_active_learning.py --max 50
```

- Outputs `data/uncertain_samples.txt` — ranked image paths
- Creates `data/label_studio_tasks.json` — ready to import into Label Studio

#### Manual Annotation Workflow

1. Import `data/label_studio_tasks.json` into [Label Studio](https://labelstud.io/)
2. Correct bounding boxes and labels
3. Export corrected annotations to `data/manual_annotations/`
4. Merge with existing YOLO labels and retrain:

```powershell
python scripts/05_train_yolo.py --epochs 50
```

### Step 6: Predict on New PDF

Run layout detection on any PDF:

```powershell
# Auto-detect: heuristics for text PDFs, model for scanned
python scripts/06_predict_pdf.py --pdf path/to/document.pdf

# Force YOLO model
python scripts/06_predict_pdf.py --pdf path/to/document.pdf --force-model

# Draw bounding boxes on images
python scripts/06_predict_pdf.py --pdf path/to/document.pdf --draw --output results/
```

### Run All Steps at Once

Use the master pipeline script:

```powershell
# Run everything
python run_pipeline.py --max-docs 200

# Run specific steps only
python run_pipeline.py --steps 1 2 3

# Skip training
python run_pipeline.py --skip-train
```

---

## Heuristic Classification Rules

The pdfplumber extraction applies the following rules to classify text blocks:

| Class | Detection Rule |
|-------|---------------|
| **header** | Top 12% of page + Vietnamese header keywords ("CỘNG HÒA…", "Số:") or small font |
| **title** | Font ≥ 1.3× median + title keywords ("QUYẾT ĐỊNH", "NGHỊ ĐỊNH") |
| **article** | Text starts with "Điều" + number |
| **paragraph** | Default for standard text blocks |
| **list** | Lines starting with `a)`, `1.`, `-`, `+`, or `•` |
| **table** | Detected via `pdfplumber.find_tables()` (grid-line analysis) |
| **signature** | Bottom 30% + keywords ("Ký tên", "TM.", "CHỦ TỊCH") |
| **footer** | Bottom 12% of page + keywords ("Trang", "Nơi nhận:") or small font |

All thresholds are configurable in `config/config.yaml` under `heuristics`.

---

## Output Format

Layout annotations are saved as JSON:

```json
[
  {
    "page": 1,
    "width": 595.276,
    "height": 841.89,
    "elements": [
      {
        "type": "header",
        "bbox": [72.0, 36.0, 523.0, 85.0],
        "text": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "confidence": 0.90
      },
      {
        "type": "title",
        "bbox": [150.0, 120.0, 445.0, 155.0],
        "text": "QUYẾT ĐỊNH",
        "confidence": 0.95
      }
    ]
  }
]
```

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `pdf2image` fails on Windows | Install Poppler and set `poppler.path` in `config.yaml` |
| API returns 403/429 errors | Reduce `page_size`, increase `retry_delay` in config |
| Low detection quality | Run active learning (step 5), manually correct, and retrain |
| CUDA out of memory | Reduce `batch_size` or `image_size` in config |
| No text extracted from PDF | The PDF is likely scanned; use `--force-model` for YOLO inference |

---

## License

This project is for educational and research purposes. The legal documents are sourced from the public Vietnamese legal database (vbpl.vn).
