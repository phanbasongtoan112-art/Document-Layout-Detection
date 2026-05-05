# VBPL PDF Layout Detection Pipeline

This repository provides a complete data pipeline to crawl legal PDF documents from [vbpl.vn](https://vbpl.vn), convert them to images, and perform advanced layout detection using a pre-trained DocLayNet YOLO model.

## 📑 Table of Contents
1. [Project Goal & Key Results](#-project-goal--key-results)
2. [Folder Structure](#-folder-structure)
3. [Prerequisites](#-prerequisites)
4. [Installation Guide](#-installation-guide)
5. [Usage Instructions](#-usage-instructions)
   - [1. Download PDFs](#1-download-pdfs)
   - [2. Convert PDFs to Images](#2-convert-pdfs-to-images)
   - [3. Run Layout Detection](#3-run-layout-detection)
   - [4. Visualize Predictions](#4-visualize-predictions)
6. [Results & Output Format](#-results--output-format)
7. [GitHub Workflow for Collaborators](#-github-workflow-for-collaborators)
8. [Troubleshooting](#-troubleshooting)
9. [License](#-license)

---

## 🎯 Project Goal & Key Results

**Goal:** Automate the acquisition of Vietnamese legal texts and extract structured layout elements (such as Title, Text, Table, List-item, etc.) for further NLP and Data Science applications.

**Key Results:**
- **Acquisition:** Successfully downloaded 287 PDF documents from vbpl.vn.
- **Preprocessing:** Converted the PDFs into 1,672 high-quality PNG images.
- **Inference:** Achieved a **99.7% detection rate** (1,667 out of 1,672 images had valid detections).
- **Objects Detected:** Successfully detected and localized **9,085 layout objects** across the dataset.

---

## 📂 Folder Structure

```text
vbpl-layout-detection/
├── data/                     
│   ├── images/               # Generated PNG images (git-ignored)
│   └── pdfs/                 # Downloaded PDFs (git-ignored)
├── models/
│   └── yolo26n_doc_layout.pt # Pre-trained DocLayNet YOLO model
├── predictions/
│   └── doclaynet_pdf/        # Output from layout detection
│       ├── labels/           # YOLO format .txt bounding boxes
│       ├── predictions.json  # Comprehensive JSON results
│       └── summary.csv       # Summary statistics per image
├── scripts/
│   ├── convert_pdf_to_images.py
│   ├── run_doclaynet_inference.py
│   └── vbpl_download.py
├── visualize_predictions.py  # Script for visualizing bounding boxes
├── requirements.txt          # Python dependencies
├── GIT_WORKFLOW.md           # Solo developer git guide
└── README.md                 # Project documentation
```

---

## ⚙️ Prerequisites

To run this project, especially on Windows, you will need:
1. **Python 3.10**: Make sure Python is added to your system `PATH`.
2. **Git**: Installed and configured on your machine.
3. **Poppler for Windows**: Required by the `pdf2image` library.
   - Download the latest Poppler Windows binaries from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases).
   - Extract the `.zip` file to a location like `C:\poppler`.
   - Add the `C:\poppler\Library\bin` directory to your system's `PATH` Environment Variable.

---

## 🚀 Installation Guide

Run the following commands in **PowerShell**:

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/PhanBaSongToan/vbpl-layout-detection.git
   cd vbpl-layout-detection
   ```

2. **Set up a Virtual Environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

---

## 💡 Usage Instructions

### 1. Download PDFs
Fetch PDF files directly from the VBPL database.
```powershell
python scripts/vbpl_download.py --limit 300 --resume
```
**Arguments:**
- `--limit` (optional): Maximum number of PDFs to download.
- `--resume` (optional): Skip already downloaded files and pick up where you left off.

### 2. Convert PDFs to Images
Convert the downloaded PDF documents into PNG format for YOLO inference.
```powershell
python scripts/convert_pdf_to_images.py --input data/pdfs --output data/images --dpi 300
```
**Arguments:**
- `--input`: Folder containing the downloaded `.pdf` files.
- `--output`: Folder where `.png` images will be saved.
- `--dpi` (optional): Resolution of the output images (default: `300`).

### 3. Run Layout Detection
Run the pre-trained DocLayNet YOLO model on the generated images.
```powershell
python scripts/run_doclaynet_inference.py --input data/images --output predictions/doclaynet_pdf --conf 0.25 --device cpu
```
**Arguments:**
- `--input`: Folder containing the `.png` images.
- `--output`: Folder to save YOLO labels, JSON, and CSV.
- `--conf` (optional): Confidence threshold for detections (default: `0.25`).
- `--device` (optional): Compute device to use (`cpu` or `cuda:0` for GPU).
- `--resume` (optional): Skip images that already exist in `predictions.json`.

### 4. Visualize Predictions
Draw bounding boxes over an original image to verify layout detection quality.
```powershell
python visualize_predictions.py --image "data/images/sample_page_1.png" --label-dir "predictions/doclaynet_pdf/labels" --output "annotated_sample.png" --conf 0.25
```
**Arguments:**
- `--image` (required): Path to the input PNG image.
- `--label-dir` (optional): Directory containing the corresponding YOLO `.txt` files.
- `--output` (optional): Path to save the annotated image (default: `annotated.png`).
- `--conf` (optional): Filter drawn boxes by confidence threshold.

---

## 📊 Results & Output Format

After running layout detection, results are saved in the `predictions/doclaynet_pdf/` directory:
1. **`predictions.json`**: A master file containing the filename, class names (e.g., `Title`, `Text`, `List-item`), exact bounding box coordinates `[x1, y1, x2, y2]`, and confidence scores for all processed images.
2. **`summary.csv`**: A spreadsheet summarizing total boxes, classes detected, and average confidence per image.
3. **`labels/` Folder**: YOLO-format text files (one per image). Each row represents a bounding box: `class_id x_center y_center width height`.

*(Note: Data folders like `data/images/` and `data/pdfs/` are excluded via `.gitignore` to keep the repository lightweight.)*

---

## 🤝 GitHub Workflow for Collaborators

If you want to contribute to this project, follow this standard Git flow:

1. **Fork the Repo**: Click the "Fork" button at the top right of this page.
2. **Clone your Fork locally**:
   ```powershell
   git clone https://github.com/YOUR_USERNAME/vbpl-layout-detection.git
   cd vbpl-layout-detection
   ```
3. **Create a Feature Branch**:
   ```powershell
   git checkout -b feature/add-new-model
   ```
4. **Make Changes, Commit, and Push**:
   ```powershell
   git add .
   git commit -m "feat: implement new model inference logic"
   git push origin feature/add-new-model
   ```
5. **Open a Pull Request (PR)**: Go to the original repository on GitHub and open a PR from your new branch to the `main` branch.
6. **Code Review & Merge**: Once approved, your code will be merged into `main`.
7. **Keep your local `main` updated**:
   ```powershell
   git checkout main
   git pull origin main
   ```

---

## 🛠️ Troubleshooting

- **`pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count.`**
  - **Cause:** Poppler is not installed or not in your system PATH.
  - **Fix:** Download Poppler, extract it, and add the `bin/` folder to your Windows Environment Variables. Restart your PowerShell or IDE afterward.

- **`CUDA Out of Memory` (when using GPU)**
  - **Cause:** The images are too large, or batch size is too high for your GPU VRAM.
  - **Fix:** Switch `--device` to `cpu` or resize the images before running inference.

- **Missing system libraries for OpenCV**
  - **Cause:** OpenCV requires certain media frameworks.
  - **Fix:** If you are running this in Docker or WSL, ensure you have `libgl1` and `libglib2.0-0` installed (`apt-get update && apt-get install libgl1 libglib2.0-0`). On standard Windows, the pip package usually handles this automatically.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
