"""
run_doclaynet_inference.py — Run inference on document images using a pre-trained DocLayNet YOLO model.

This script processes a directory of images and generates:
1. YOLO format text files (one per image) containing normalized bounding boxes.
2. A single predictions.json file containing all detections (x1, y1, x2, y2, confidence, class).
3. A summary.csv file with per-image statistics (total boxes, classes detected, average confidence).

Usage:
    # Run with default settings (CPU, conf=0.25)
    python scripts/run_doclaynet_inference.py

    # Run on GPU with higher confidence
    python scripts/run_doclaynet_inference.py --device cuda --conf 0.5

    # Resume interrupted processing
    python scripts/run_doclaynet_inference.py --resume
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
from tqdm import tqdm
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("doclaynet_inference")

def parse_args():
    parser = argparse.ArgumentParser(description="Run DocLayNet YOLO inference on images.")
    parser.add_argument("--model", type=str, default="models/yolo26n_doc_layout.pt",
                        help="Path to the YOLO model file.")
    parser.add_argument("--input", type=str, default="data/images",
                        help="Directory containing input images.")
    parser.add_argument("--output", type=str, default="predictions/doclaynet_pdf",
                        help="Directory to save output predictions.")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Confidence threshold for detections.")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Device to run inference on (e.g., 'cpu', 'cuda', 'cuda:0').")
    
    # Adding BooleanOptionalAction allows --save-txt and --no-save-txt
    parser.add_argument("--save-txt", action=argparse.BooleanOptionalAction, default=True,
                        help="Save YOLO format .txt files.")
    
    parser.add_argument("--resume", action="store_true",
                        help="Skip images that already have a corresponding .txt output.")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Resolve paths relative to the project root (assuming script is in scripts/)
    project_root = Path(__file__).resolve().parent.parent
    
    model_path = Path(args.model) if Path(args.model).is_absolute() else project_root / args.model
    input_dir = Path(args.input) if Path(args.input).is_absolute() else project_root / args.input
    output_dir = Path(args.output) if Path(args.output).is_absolute() else project_root / args.output
    
    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        logger.info("Please ensure you have downloaded or placed the pre-trained model in the correct path.")
        sys.exit(1)
        
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
        
    # Prepare output directories
    labels_dir = output_dir / "labels"
    os.makedirs(labels_dir, exist_ok=True)
    
    json_path = output_dir / "predictions.json"
    csv_path = output_dir / "summary.csv"
    
    # Load model
    logger.info(f"Loading YOLO model from {model_path} on device '{args.device}'...")
    try:
        model = YOLO(model_path)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)
        
    # Gather images
    valid_exts = {".png", ".jpg", ".jpeg"}
    image_paths = [p for p in input_dir.iterdir() if p.suffix.lower() in valid_exts]
    
    if not image_paths:
        logger.warning(f"No valid images found in {input_dir}")
        return
        
    logger.info(f"Found {len(image_paths)} images to process.")
    
    # Data structures for JSON and CSV outputs
    all_predictions = []
    summary_data = []
    
    # Handle resume logic
    processed_stems = set()
    if args.resume:
        # Check existing labels
        if labels_dir.exists():
            for txt_file in labels_dir.glob("*.txt"):
                processed_stems.add(txt_file.stem)
                
        # Attempt to load existing JSON and CSV to append to them
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    all_predictions = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load existing {json_path}: {e}")
                
        if csv_path.exists():
            try:
                df_exist = pd.read_csv(csv_path)
                summary_data = df_exist.to_dict('records')
            except Exception as e:
                logger.warning(f"Could not load existing {csv_path}: {e}")
                
        logger.info(f"Resuming... found {len(processed_stems)} already processed images.")
        
    # Counters for the summary
    images_processed = 0
    images_with_detections = 0
    total_objects_detected = 0
    
    # Inference loop
    for img_path in tqdm(image_paths, desc="Running Inference"):
        if args.resume and img_path.stem in processed_stems:
            continue
            
        try:
            # verbose=False suppresses the standard YOLO per-image printing
            results = model.predict(source=str(img_path), conf=args.conf, device=args.device, verbose=False)
            result = results[0]  # We only process one image at a time
            
            # Prepare data
            filename = img_path.name
            img_predictions = {
                "filename": filename,
                "elements": []
            }
            
            boxes = result.boxes
            num_boxes = len(boxes)
            
            total_objects_detected += num_boxes
            if num_boxes > 0:
                images_with_detections += 1
                
            sum_conf = 0.0
            classes_detected = set()
            txt_content = []
            
            for box in boxes:
                # Extract box details
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]
                conf = float(box.conf[0])
                
                # xyxy provides [x1, y1, x2, y2] absolute pixel coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # xywhn provides [x_center, y_center, width, height] normalized coordinates for YOLO txt
                cx, cy, nw, nh = box.xywhn[0].tolist()
                
                # Accumulate metrics
                sum_conf += conf
                classes_detected.add(cls_name)
                
                # Add to JSON output
                img_predictions["elements"].append({
                    "type": cls_name,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2]
                })
                
                # Add to TXT output
                txt_content.append(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                
            all_predictions.append(img_predictions)
            
            # Add to CSV summary data
            avg_conf = (sum_conf / num_boxes) if num_boxes > 0 else 0.0
            summary_data.append({
                "image_name": filename,
                "total_boxes": num_boxes,
                "classes_detected": ", ".join(sorted(list(classes_detected))),
                "avg_confidence": round(avg_conf, 4)
            })
            
            # Save YOLO TXT file
            if args.save_txt:
                txt_path = labels_dir / f"{img_path.stem}.txt"
                with open(txt_path, 'w', encoding='utf-8') as f:
                    if txt_content:
                        f.write("\n".join(txt_content) + "\n")
                    else:
                        # Create an empty file to indicate it was processed but nothing was found
                        f.write("")
                        
            images_processed += 1
            
        except Exception as e:
            logger.error(f"Error processing {img_path.name}: {e}")
            
    # Save JSON file
    if all_predictions:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_predictions, f, indent=2, ensure_ascii=False)
            
    # Save CSV file
    if summary_data:
        df = pd.DataFrame(summary_data)
        df.to_csv(csv_path, index=False)
        
    # Print final summary
    logger.info("=" * 60)
    logger.info("Inference Summary:")
    logger.info(f"  Total images processed:       {images_processed}")
    logger.info(f"  Images with detections:       {images_with_detections}")
    logger.info(f"  Total objects detected:       {total_objects_detected}")
    logger.info(f"  JSON predictions saved to:    {json_path}")
    logger.info(f"  CSV summary saved to:         {csv_path}")
    if args.save_txt:
        logger.info(f"  YOLO format txt saved to:     {labels_dir}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
