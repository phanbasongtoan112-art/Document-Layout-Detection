import argparse
import os
from pathlib import Path

import cv2

# Alphabetical class names as standard in DocLayNet YOLO models.
# (0: Caption, 1: Footnote, 2: Formula, 3: List-item, 4: Page-footer,
#  5: Page-header, 6: Picture, 7: Section-header, 8: Table, 9: Text, 10: Title)
CLASSES = [
    "Caption", "Footnote", "Formula", "List-item", "Page-footer", 
    "Page-header", "Picture", "Section-header", "Table", "Text", "Title"
]

def parse_args():
    parser = argparse.ArgumentParser(description="Visualize YOLO predictions on images")
    parser.add_argument("--image", type=str, required=True, help="Path to input PNG image")
    parser.add_argument("--output", type=str, default="annotated.png", help="Path to save output image")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (if present in labels)")
    parser.add_argument("--label-dir", type=str, default="predictions/doclaynet_pdf/labels", help="Directory containing .txt label files")
    return parser.parse_args()

def main():
    args = parse_args()
    
    img_path = Path(args.image)
    label_dir = Path(args.label_dir)
    output_path = Path(args.output)
    
    if not img_path.exists():
        print(f"Error: Image file '{img_path}' not found.")
        return
        
    # Read the image
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"Error: Could not load image '{img_path}'.")
        return
        
    img_h, img_w = img.shape[:2]
    
    # Find corresponding label file
    label_file = label_dir / f"{img_path.stem}.txt"
    
    if not label_file.exists():
        print(f"Warning: Label file '{label_file}' not found. Saving original image.")
        cv2.imwrite(str(output_path), img)
        print(f"Successfully saved to '{output_path}'")
        return
        
    # Read labels and draw bounding boxes
    with open(label_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
            
        cls_id = int(parts[0])
        x_center = float(parts[1])
        y_center = float(parts[2])
        width = float(parts[3])
        height = float(parts[4])
        
        conf = None
        # YOLO format can sometimes have confidence as the 6th value
        if len(parts) >= 6:
            conf = float(parts[5])
            if conf < args.conf:
                continue
                
        # Convert normalized YOLO format to pixel coordinates
        x1 = int((x_center - width / 2) * img_w)
        y1 = int((y_center - height / 2) * img_h)
        x2 = int((x_center + width / 2) * img_w)
        y2 = int((y_center + height / 2) * img_h)
        
        # Ensure coordinates are within image boundaries
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img_w - 1, x2), min(img_h - 1, y2)
        
        # Get class name
        cls_name = CLASSES[cls_id] if cls_id < len(CLASSES) else f"Class_{cls_id}"
        
        # Prepare label text
        label_text = f"{cls_name}"
        if conf is not None:
            label_text += f" {conf:.2f}"
            
        # Draw bounding box (green color: BGR format, so (0, 255, 0))
        color = (0, 255, 0)
        thickness = 2
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        
        # Draw label background and text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 1
        
        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, font_thickness)
        
        # Draw filled rectangle for text background
        # Handle case where text is at the very top of the image
        bg_y1 = y1 - text_h - baseline - 4
        bg_y2 = y1
        text_y = y1 - baseline - 2
        
        if bg_y1 < 0:
            bg_y1 = y1
            bg_y2 = y1 + text_h + baseline + 4
            text_y = bg_y2 - baseline - 2
            
        cv2.rectangle(img, (x1, bg_y1), (x1 + text_w + 4, bg_y2), color, -1)
        
        # Draw text (black)
        cv2.putText(img, label_text, (x1 + 2, text_y), font, font_scale, (0, 0, 0), font_thickness, cv2.LINE_AA)
        
    # Save the output image
    success = cv2.imwrite(str(output_path), img)
    if success:
        print(f"Successfully saved annotated image to '{output_path}'")
    else:
        print(f"Error: Failed to save image to '{output_path}'")

if __name__ == "__main__":
    main()
