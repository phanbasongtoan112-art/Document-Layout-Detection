"""
convert_pdf_to_images.py — Convert PDF files to PNG/JPG images (one per page).

Converts every page of every PDF in the input directory into individual images
using the pdf2image library (which wraps Poppler). Designed for the Vietnamese
legal document layout detection pipeline.

Prerequisites:
    pip install pdf2image tqdm Pillow

    Poppler must also be installed:
      - Windows:  choco install poppler   (or download from
                  https://github.com/oschwartz10612/poppler-windows/releases
                  and add the bin/ folder to your PATH or use --poppler-path)
      - Linux:    sudo apt install poppler-utils
      - macOS:    brew install poppler

Usage:
    # Default: convert data/pdfs/*.pdf → data/images/ at 200 DPI
    python scripts/convert_pdf_to_images.py

    # Custom settings
    python scripts/convert_pdf_to_images.py --input data/pdfs --output data/images --dpi 300

    # Force overwrite existing images
    python scripts/convert_pdf_to_images.py --force

    # Specify Poppler path explicitly (Windows)
    python scripts/convert_pdf_to_images.py --poppler-path "C:/poppler-24.08.0/Library/bin"

    # Output as JPEG instead of PNG
    python scripts/convert_pdf_to_images.py --format jpg
"""

import argparse
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pdf_to_images")


# ---------------------------------------------------------------------------
# Poppler Detection
# ---------------------------------------------------------------------------

def find_poppler_path() -> Optional[str]:
    """
    Try to locate the Poppler binaries automatically.
    Returns the path to the bin/ directory, or None if not found.
    """
    # 1. Check if pdftoppm is already on PATH
    if shutil.which("pdftoppm"):
        return None  # pdf2image will find it via PATH

    # 2. Common Windows installation paths
    common_paths = [
        r"C:\poppler-26.02.0\Library\bin",
        r"C:\poppler-24.08.0\Library\bin",
        r"C:\poppler\Library\bin",
        r"C:\poppler\bin",
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
        r"C:\tools\poppler\Library\bin",
        r"C:\ProgramData\chocolatey\lib\poppler\tools\Library\bin",
    ]

    for p in common_paths:
        if os.path.isfile(os.path.join(p, "pdftoppm.exe")):
            return p

    return None


def verify_poppler(poppler_path: Optional[str] = None) -> Optional[str]:
    """
    Verify Poppler is available. Returns the resolved poppler_path or None.
    Exits with a helpful message if Poppler is not found.
    """
    if poppler_path and os.path.isdir(poppler_path):
        pdftoppm = os.path.join(poppler_path, "pdftoppm.exe" if sys.platform == "win32" else "pdftoppm")
        if os.path.isfile(pdftoppm):
            logger.info("Using Poppler from: %s", poppler_path)
            return poppler_path
        else:
            logger.error("Specified --poppler-path does not contain pdftoppm: %s", poppler_path)
            sys.exit(1)

    # Auto-detect
    detected = find_poppler_path()
    if detected:
        logger.info("Auto-detected Poppler at: %s", detected)
        return detected

    # pdftoppm on PATH?
    if shutil.which("pdftoppm"):
        logger.info("Poppler found on system PATH.")
        return None  # pdf2image uses PATH

    # Not found — print helpful instructions and exit
    logger.error("=" * 60)
    logger.error("Poppler NOT FOUND!")
    logger.error("=" * 60)
    logger.error("")
    logger.error("pdf2image requires Poppler to convert PDFs to images.")
    logger.error("")
    if sys.platform == "win32":
        logger.error("Install on Windows:")
        logger.error("  Option 1: choco install poppler")
        logger.error("  Option 2: Download from:")
        logger.error("    https://github.com/oschwartz10612/poppler-windows/releases")
        logger.error("    Extract and add the bin/ folder to your PATH,")
        logger.error("    or pass it via: --poppler-path \"C:/path/to/poppler/Library/bin\"")
    else:
        logger.error("Install on Linux:  sudo apt install poppler-utils")
        logger.error("Install on macOS:  brew install poppler")
    logger.error("")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Core Conversion
# ---------------------------------------------------------------------------

def convert_single_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int,
    fmt: str,
    force: bool,
    poppler_path: Optional[str],
) -> dict:
    """
    Convert a single PDF to images. Returns a stats dict.
    """
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

    stats = {"pages_converted": 0, "pages_skipped": 0, "error": None}
    stem = Path(pdf_path).stem  # e.g. "6b345d30-3e47-11f1-827d-d596bb87dbde"
    ext = fmt.lower()

    try:
        # First, get page count to check which pages need conversion
        # Convert all pages at once (more efficient than one-by-one for typical docs)
        kwargs = {
            "pdf_path": pdf_path,
            "dpi": dpi,
            "fmt": fmt.upper() if fmt.lower() == "png" else "JPEG",
        }
        if poppler_path:
            kwargs["poppler_path"] = poppler_path

        # Check if all output files already exist (fast skip)
        if not force:
            # We need to know how many pages there are first.
            # Use pdfinfo to get page count without converting.
            try:
                from pdf2image import pdfinfo_from_path
                info_kwargs = {"pdf_path": pdf_path}
                if poppler_path:
                    info_kwargs["poppler_path"] = poppler_path
                info = pdfinfo_from_path(**info_kwargs)
                total_pages = info.get("Pages", 0)
            except Exception:
                total_pages = 0  # Will convert and find out

            if total_pages > 0:
                all_exist = True
                for page_num in range(1, total_pages + 1):
                    out_file = os.path.join(output_dir, f"{stem}_page_{page_num}.{ext}")
                    if not os.path.exists(out_file):
                        all_exist = False
                        break
                if all_exist:
                    stats["pages_skipped"] = total_pages
                    return stats

        # Convert PDF to images
        images = convert_from_path(**kwargs)

        for page_num, image in enumerate(images, start=1):
            out_file = os.path.join(output_dir, f"{stem}_page_{page_num}.{ext}")

            if not force and os.path.exists(out_file):
                stats["pages_skipped"] += 1
                continue

            if ext == "jpg" or ext == "jpeg":
                image.save(out_file, "JPEG", quality=95)
            else:
                image.save(out_file, "PNG")

            stats["pages_converted"] += 1

        return stats

    except PDFInfoNotInstalledError:
        stats["error"] = "Poppler not installed or not found"
    except PDFPageCountError:
        stats["error"] = "Could not determine page count (corrupted PDF?)"
    except PDFSyntaxError:
        stats["error"] = "PDF syntax error (corrupted or encrypted PDF)"
    except PermissionError as e:
        stats["error"] = f"Permission denied: {e}"
    except Exception as e:
        stats["error"] = f"{type(e).__name__}: {e}"

    return stats


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run(
    input_dir: str,
    output_dir: str,
    dpi: int,
    fmt: str,
    force: bool,
    poppler_path: Optional[str],
):
    # Validate input directory
    if not os.path.isdir(input_dir):
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    # Collect PDF files
    pdf_files = sorted([
        f for f in os.listdir(input_dir)
        if f.lower().endswith(".pdf")
    ])

    if not pdf_files:
        logger.warning("No PDF files found in: %s", input_dir)
        return

    logger.info("Found %d PDF files in: %s", len(pdf_files), input_dir)
    logger.info("Output directory: %s", output_dir)
    logger.info("DPI: %d | Format: %s | Force: %s", dpi, fmt.upper(), force)

    os.makedirs(output_dir, exist_ok=True)

    # Process
    total_stats = {
        "pdfs_processed": 0,
        "pdfs_skipped": 0,
        "pdfs_errored": 0,
        "pages_converted": 0,
        "pages_skipped": 0,
        "errors": [],
    }

    for pdf_name in tqdm(pdf_files, desc="Converting PDFs", unit="pdf"):
        pdf_path = os.path.join(input_dir, pdf_name)

        stats = convert_single_pdf(
            pdf_path=pdf_path,
            output_dir=output_dir,
            dpi=dpi,
            fmt=fmt,
            force=force,
            poppler_path=poppler_path,
        )

        if stats["error"]:
            logger.warning("  ✗ %s: %s", pdf_name, stats["error"])
            total_stats["pdfs_errored"] += 1
            total_stats["errors"].append((pdf_name, stats["error"]))
        elif stats["pages_converted"] == 0 and stats["pages_skipped"] > 0:
            total_stats["pdfs_skipped"] += 1
            total_stats["pages_skipped"] += stats["pages_skipped"]
        else:
            total_stats["pdfs_processed"] += 1
            total_stats["pages_converted"] += stats["pages_converted"]
            total_stats["pages_skipped"] += stats["pages_skipped"]

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Conversion Summary:")
    logger.info("  PDFs converted:     %d", total_stats["pdfs_processed"])
    logger.info("  PDFs skipped:       %d (all pages already existed)", total_stats["pdfs_skipped"])
    logger.info("  PDFs with errors:   %d", total_stats["pdfs_errored"])
    logger.info("  Pages converted:    %d", total_stats["pages_converted"])
    logger.info("  Pages skipped:      %d (already existed)", total_stats["pages_skipped"])
    logger.info("=" * 60)

    if total_stats["errors"]:
        logger.info("")
        logger.info("Errors encountered:")
        for pdf_name, error_msg in total_stats["errors"]:
            logger.info("  • %s: %s", pdf_name, error_msg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert PDF files to PNG/JPG images (one per page).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python scripts/convert_pdf_to_images.py
  python scripts/convert_pdf_to_images.py --dpi 300 --format jpg
  python scripts/convert_pdf_to_images.py --force
  python scripts/convert_pdf_to_images.py --poppler-path "C:/poppler/Library/bin"
        """,
    )
    parser.add_argument(
        "--input", type=str, default="data/pdfs",
        help="Directory containing PDF files (default: data/pdfs).",
    )
    parser.add_argument(
        "--output", type=str, default="data/images",
        help="Directory to save images (default: data/images).",
    )
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="Image resolution in DPI (default: 200).",
    )
    parser.add_argument(
        "--format", type=str, default="png", choices=["png", "jpg", "jpeg"],
        help="Output image format (default: png).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing images.",
    )
    parser.add_argument(
        "--poppler-path", type=str, default=None,
        help="Explicit path to Poppler bin/ directory (Windows).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = Path(__file__).resolve().parent.parent

    input_dir = (
        Path(args.input)
        if Path(args.input).is_absolute()
        else project_root / args.input
    )
    output_dir = (
        Path(args.output)
        if Path(args.output).is_absolute()
        else project_root / args.output
    )

    # Verify Poppler before starting
    poppler_path = verify_poppler(args.poppler_path)

    run(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        dpi=args.dpi,
        fmt=args.format,
        force=args.force,
        poppler_path=poppler_path,
    )


if __name__ == "__main__":
    main()
