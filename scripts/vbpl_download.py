"""
01_vbpl_download.py — Download legal document PDFs from vbpl.vn via public API

This script uses the official vbpl.vn REST APIs to:
1. Fetch a paginated list of document IDs.
2. Retrieve metadata (including PDF filename) for each document.
3. Download the PDF binary via the MinIO download endpoint.

No Selenium required — pure requests-based.

Usage:
    # Download up to 100 PDFs (default)
    python scripts/01_vbpl_download.py

    # Download 500 PDFs with 2s delay, saving to a custom folder
    python scripts/01_vbpl_download.py --limit 500 --delay 2 --output-dir data/vbpl_pdfs

    # Resume a previous interrupted run
    python scripts/01_vbpl_download.py --limit 500 --resume

    # Force re-download everything
    python scripts/01_vbpl_download.py --no-resume
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vbpl_download")

# ---------------------------------------------------------------------------
# API Configuration
# ---------------------------------------------------------------------------
API_GATEWAY = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc"

LIST_URL = f"{API_GATEWAY}/all"
DETAIL_URL = f"{API_GATEWAY}/{{doc_id}}"
DOWNLOAD_URL = f"{API_GATEWAY}/minio/buckets/files/download"

BUCKET_NAME = "vbpl"

COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://vbpl.vn/",
    "Origin": "https://vbpl.vn",
    "Accept": "application/json",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

# How many IDs per page when listing documents
PAGE_SIZE = 50

# Max retries per request
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------

def create_session() -> requests.Session:
    """Create a requests.Session with pre-configured headers."""
    session = requests.Session()
    session.headers.update(COMMON_HEADERS)
    return session


# ---------------------------------------------------------------------------
# API Calls
# ---------------------------------------------------------------------------

def fetch_document_ids(session: requests.Session, limit: int) -> List[str]:
    """
    Fetch document IDs from the list API with pagination.

    The API expects a POST with JSON body:
        {"pageNumber": 1, "pageSize": 50, "matchMode": "all_words", "optionDoc": "title"}

    Response shape:
        {"success": true, "data": {"current": 1, "total": 166891, "items": [{"id": "...", ...}]}}

    Pages are 1-indexed.
    Returns up to `limit` IDs.
    """
    all_ids: List[str] = []
    page_number = 1  # API uses 1-indexed pages

    logger.info("Fetching document IDs (limit=%d, page_size=%d)...", limit, PAGE_SIZE)

    with tqdm(total=limit, desc="Fetching IDs", unit="id") as pbar:
        while len(all_ids) < limit:
            remaining = limit - len(all_ids)
            current_page_size = min(PAGE_SIZE, remaining)

            payload = {
                "pageNumber": page_number,
                "pageSize": current_page_size,
                "matchMode": "all_words",
                "optionDoc": "title",
            }

            resp = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = session.post(
                        LIST_URL,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    break
                except requests.RequestException as e:
                    logger.warning(
                        "  List API error (page=%d, attempt %d/%d): %s",
                        page_number, attempt, MAX_RETRIES, e,
                    )
                    if attempt == MAX_RETRIES:
                        logger.error(
                            "  Giving up on page %d after %d attempts.",
                            page_number, MAX_RETRIES,
                        )
                        return all_ids
                    time.sleep(2 * attempt)

            if resp is None:
                break

            body = resp.json()

            # Validate top-level success flag
            if not body.get("success", False):
                logger.warning(
                    "  API returned success=false on page %d: %s",
                    page_number, body.get("message", "unknown error"),
                )
                break

            # Navigate: body -> data -> items
            ids_on_page = _extract_ids_from_response(body)

            if not ids_on_page:
                logger.info("  No more IDs returned on page %d. Stopping.", page_number)
                break

            all_ids.extend(ids_on_page)
            pbar.update(len(ids_on_page))

            # Log total available for reference (first page only)
            if page_number == 1:
                total_available = (body.get("data") or {}).get("total", "?")
                logger.info("  Total documents available on server: %s", total_available)

            # If fewer results than requested, we've reached the last page
            if len(ids_on_page) < current_page_size:
                logger.info(
                    "  Last page reached (got %d < %d).",
                    len(ids_on_page), current_page_size,
                )
                break

            page_number += 1
            time.sleep(random.uniform(0.3, 0.8))

    # Trim to exact limit
    all_ids = all_ids[:limit]
    logger.info("Total document IDs fetched: %d", len(all_ids))
    return all_ids


def _extract_ids_from_response(body: Any) -> List[str]:
    """
    Extract document IDs from the list API response.

    Expected structure:
        {"success": true, "data": {"current": 1, "total": N, "items": [{"id": "..."}]}}

    Falls back to searching alternative shapes if the expected one is absent.
    """
    ids: List[str] = []

    if not isinstance(body, dict):
        return ids

    # Primary path: body -> data -> items
    data_obj = body.get("data")
    if isinstance(data_obj, dict):
        items = data_obj.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    doc_id = item.get("id")
                    if doc_id:
                        ids.append(str(doc_id))

    # If primary path yielded nothing, try fallback shapes
    if not ids:
        # Fallback 1: body -> data is a list directly
        if isinstance(data_obj, list):
            for item in data_obj:
                if isinstance(item, dict):
                    doc_id = item.get("id") or item.get("documentId")
                    if doc_id:
                        ids.append(str(doc_id))
        # Fallback 2: body -> content (Spring Boot Page)
        content = body.get("content", [])
        if not ids and isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    doc_id = item.get("id")
                    if doc_id:
                        ids.append(str(doc_id))

    return ids


def fetch_document_detail(
    session: requests.Session, doc_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch document metadata from the detail API.
    Returns the JSON response dict, or None on failure.
    """
    url = DETAIL_URL.format(doc_id=doc_id)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(
                "  Detail API error for %s (attempt %d/%d): %s",
                doc_id, attempt, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)

    return None


def download_pdf(
    session: requests.Session,
    doc_id: str,
    pdf_filename: str,
    dest_path: str,
) -> bool:
    """
    Download a PDF using the MinIO download endpoint (POST with JSON payload).
    Streams the response to disk. Returns True on success.
    """
    payload = {
        "bucketName": BUCKET_NAME,
        "folderName": doc_id,
        "objectName": pdf_filename,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(
                DOWNLOAD_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=120,
            )

            if resp.status_code != 200:
                logger.warning(
                    "    Download HTTP %d for %s (attempt %d/%d)",
                    resp.status_code, pdf_filename, attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                continue

            # Verify we actually got a PDF (not an error HTML page)
            content_type = resp.headers.get("Content-Type", "")
            first_chunk = b""

            with open(dest_path, "wb") as fh:
                for i, chunk in enumerate(resp.iter_content(chunk_size=8192)):
                    if i == 0:
                        first_chunk = chunk
                    fh.write(chunk)

            # Validate downloaded file
            file_size = os.path.getsize(dest_path)

            if file_size < 512:
                logger.warning(
                    "    File too small (%d bytes). Likely an error response.", file_size
                )
                os.remove(dest_path)
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                continue

            if not first_chunk.startswith(b"%PDF") and b"%PDF" not in first_chunk[:1024]:
                # Check if it's JSON error
                if first_chunk.startswith(b"{") or first_chunk.startswith(b"<"):
                    logger.warning("    Got non-PDF response (JSON/HTML). Discarding.")
                    os.remove(dest_path)
                    if attempt < MAX_RETRIES:
                        time.sleep(2 * attempt)
                    continue

            logger.debug("    Downloaded %s (%d bytes)", pdf_filename, file_size)
            return True

        except requests.RequestException as e:
            logger.warning(
                "    Download error for %s (attempt %d/%d): %s",
                pdf_filename, attempt, MAX_RETRIES, e,
            )
            if os.path.exists(dest_path):
                os.remove(dest_path)
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)

    return False


# ---------------------------------------------------------------------------
# Resume Tracking
# ---------------------------------------------------------------------------

def load_done_set(output_dir: str) -> Set[str]:
    """
    Build a set of already-downloaded document IDs by scanning the output dir.
    """
    done: Set[str] = set()
    if os.path.isdir(output_dir):
        for fname in os.listdir(output_dir):
            if fname.endswith(".pdf"):
                # The filename is {doc_id}.pdf
                doc_id = fname[:-4]
                done.add(doc_id)
    return done


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run(
    output_dir: str,
    limit: int,
    delay: float,
    resume: bool,
    use_original_name: bool,
):
    os.makedirs(output_dir, exist_ok=True)
    session = create_session()

    # 1. Fetch document IDs
    doc_ids = fetch_document_ids(session, limit)
    if not doc_ids:
        logger.error("No document IDs fetched. Exiting.")
        return

    # 2. Build resume set
    done_ids = load_done_set(output_dir) if resume else set()
    if done_ids:
        logger.info("Resume mode: %d PDFs already downloaded, will skip them.", len(done_ids))

    # 3. Process each document
    stats = {"downloaded": 0, "skipped": 0, "no_pdf": 0, "failed": 0}

    try:
        for doc_id in tqdm(doc_ids, desc="Downloading PDFs", unit="doc"):
            # Skip if already downloaded
            if resume and doc_id in done_ids:
                stats["skipped"] += 1
                continue

            # 3a. Get document detail
            detail = fetch_document_detail(session, doc_id)
            if detail is None:
                logger.warning("  ✗ Could not fetch detail for: %s", doc_id)
                stats["failed"] += 1
                time.sleep(delay)
                continue

            # Extract the PDF filename from the detail response
            pdf_filename = _extract_pdf_filename(detail)
            if not pdf_filename:
                logger.warning(
                    "  ✗ No PDF filename (documentContentFileName) for: %s", doc_id
                )
                stats["no_pdf"] += 1
                time.sleep(delay * 0.5)
                continue

            # 3b. Determine destination path
            if use_original_name:
                safe_name = pdf_filename.replace("/", "_").replace("\\", "_")
                dest = os.path.join(output_dir, safe_name)
            else:
                dest = os.path.join(output_dir, f"{doc_id}.pdf")

            # 3c. Download
            logger.info("  Downloading: %s → %s", pdf_filename, os.path.basename(dest))
            success = download_pdf(session, doc_id, pdf_filename, dest)

            if success:
                stats["downloaded"] += 1
                done_ids.add(doc_id)
            else:
                logger.warning("  ✗ Failed to download PDF for: %s", doc_id)
                stats["failed"] += 1

            # Polite delay with jitter
            sleep_time = max(0.3, delay + random.uniform(-0.3, 0.5))
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Progress is saved (resume with --resume).")

    # 4. Summary
    logger.info("=" * 60)
    logger.info("Download Summary:")
    logger.info("  Downloaded:    %d", stats["downloaded"])
    logger.info("  Skipped:       %d (already existed)", stats["skipped"])
    logger.info("  No PDF field:  %d", stats["no_pdf"])
    logger.info("  Failed:        %d", stats["failed"])
    logger.info("  Total in dir:  %d", len(done_ids))
    logger.info("=" * 60)


def _extract_pdf_filename(detail: Any) -> Optional[str]:
    """
    Extract the PDF filename from the document detail response.
    Handles nested response structures.
    """
    if isinstance(detail, dict):
        # Direct field
        fname = detail.get("documentContentFileName")
        if fname:
            return str(fname)

        # Nested under "data" or "document"
        for wrapper_key in ("data", "document", "result"):
            nested = detail.get(wrapper_key)
            if isinstance(nested, dict):
                fname = nested.get("documentContentFileName")
                if fname:
                    return str(fname)

        # Try alternative field names
        for alt_key in ("contentFileName", "pdfFileName", "fileName", "file_name"):
            fname = detail.get(alt_key)
            if fname:
                return str(fname)

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download legal document PDFs from vbpl.vn via public API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python scripts/01_vbpl_download.py --limit 50
  python scripts/01_vbpl_download.py --limit 500 --delay 2 --output-dir data/vbpl_pdfs
  python scripts/01_vbpl_download.py --limit 1000 --resume --original-name
        """,
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum number of documents to download (default: 100).",
    )
    parser.add_argument(
        "--output-dir", type=str, default="data/pdfs",
        help="Directory to save downloaded PDFs (default: data/pdfs).",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Base delay in seconds between downloads (default: 1.0).",
    )
    parser.add_argument(
        "--resume", action="store_true", default=True,
        help="Skip files that already exist (default: enabled).",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Force re-download all files, even if they exist.",
    )
    parser.add_argument(
        "--original-name", action="store_true",
        help="Save PDFs with their original filename instead of {doc_id}.pdf.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = Path(__file__).resolve().parent.parent
    out_dir = (
        Path(args.output_dir)
        if Path(args.output_dir).is_absolute()
        else project_root / args.output_dir
    )

    resume = not args.no_resume

    run(
        output_dir=str(out_dir),
        limit=args.limit,
        delay=args.delay,
        resume=resume,
        use_original_name=args.original_name,
    )


if __name__ == "__main__":
    main()
