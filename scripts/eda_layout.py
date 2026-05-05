import argparse
import os
import random
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image

def parse_args():
    parser = argparse.ArgumentParser(description="Exploratory Data Analysis for Vietnamese Legal Documents")
    parser.add_argument("--input", type=str, default="data/images", help="Input folder containing PNG images")
    parser.add_argument("--samples", type=int, default=10, help="Number of random samples to copy")
    parser.add_argument("--output-csv", type=str, default="eda_image_stats.csv", help="Output CSV file for statistics")
    parser.add_argument("--output-report", type=str, default="eda_report.md", help="Output Markdown report file")
    parser.add_argument("--sample-dir", type=str, default="eda_samples", help="Folder to save sample images")
    return parser.parse_args()

def main():
    args = parse_args()
    
    input_dir = Path(args.input)
    sample_dir = Path(args.sample_dir)
    
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return
        
    print(f"Scanning directory: {input_dir}")
    image_paths = list(input_dir.glob("*.png"))
    total_images = len(image_paths)
    
    if total_images == 0:
        print("No PNG images found in the specified input directory.")
        return
        
    print(f"Found {total_images} PNG images. Extracting properties...")
    
    data = []
    failed_images = 0
    
    # Extract properties
    for img_path in image_paths:
        file_size_kb = None
        try:
            # File size in KB
            file_size_kb = img_path.stat().st_size / 1024.0
            
            # Read image to get dimensions using Pillow
            # Pillow natively handles Unicode paths beautifully in Python 3 on Windows
            with Image.open(img_path) as img:
                width, height = img.size
                
            aspect_ratio = width / height if height > 0 else 0
            
            data.append({
                "filename": img_path.name,
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "file_size_kb": file_size_kb,
                "error": None
            })
            
        except Exception as e:
            print(f"Warning: Failed to process image '{img_path.name}'. Error: {e}")
            failed_images += 1
            data.append({
                "filename": img_path.name,
                "width": None,
                "height": None,
                "aspect_ratio": None,
                "file_size_kb": file_size_kb, # Might be None if stat failed
                "error": str(e)
            })
            
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Calculate Summary Statistics (only on successfully read images)
    # Pandas naturally ignores None/NaN values in aggregations.
    # We ensure they are numeric to avoid issues with mixed types.
    df["width"] = pd.to_numeric(df["width"])
    df["height"] = pd.to_numeric(df["height"])
    df["aspect_ratio"] = pd.to_numeric(df["aspect_ratio"])
    df["file_size_kb"] = pd.to_numeric(df["file_size_kb"])

    summary_stats = df[["width", "height", "aspect_ratio", "file_size_kb"]].agg(['min', 'max', 'mean', 'std']).round(2)
    
    print("\n--- Summary Statistics ---")
    print(summary_stats)
    print(f"\nTotal images: {total_images}")
    print(f"Successfully processed: {total_images - failed_images}")
    print(f"Failed to read: {failed_images}")
    
    # Save CSV
    df.to_csv(args.output_csv, index=False)
    print(f"\nSaved detailed statistics to {args.output_csv}")
    
    # Random Samples
    sample_dir.mkdir(parents=True, exist_ok=True)
    num_samples = min(args.samples, total_images)
    sample_paths = random.sample(image_paths, num_samples)
    
    print(f"Copying {num_samples} random samples to {sample_dir}...")
    for img_path in sample_paths:
        dest_path = sample_dir / img_path.name
        shutil.copy2(img_path, dest_path)
        
    # Generate Markdown Report
    report_content = f"""# Exploratory Data Analysis (EDA) Report
**Project:** Vietnamese Legal Document Layout Detection  
**Dataset:** PNG Images from VBPL PDFs  

## 1. Dataset Overview
- **Total Images Scanned:** {total_images}
- **Successfully Read:** {total_images - failed_images}
- **Failed to Read:** {failed_images} (Detailed errors in `{args.output_csv}`)
- **Samples Extracted:** {num_samples} (located in `{args.sample_dir}/`)

## 2. Image Statistics Summary
The following table summarizes the dimensions and file sizes of the successfully read images:

| Statistic | Width (px) | Height (px) | Aspect Ratio | File Size (KB) |
| :--- | :--- | :--- | :--- | :--- |
| **Minimum** | {summary_stats.loc['min', 'width']} | {summary_stats.loc['min', 'height']} | {summary_stats.loc['min', 'aspect_ratio']} | {summary_stats.loc['min', 'file_size_kb']} |
| **Maximum** | {summary_stats.loc['max', 'width']} | {summary_stats.loc['max', 'height']} | {summary_stats.loc['max', 'aspect_ratio']} | {summary_stats.loc['max', 'file_size_kb']} |
| **Mean** | {summary_stats.loc['mean', 'width']} | {summary_stats.loc['mean', 'height']} | {summary_stats.loc['mean', 'aspect_ratio']} | {summary_stats.loc['mean', 'file_size_kb']} |
| **Std Dev** | {summary_stats.loc['std', 'width']} | {summary_stats.loc['std', 'height']} | {summary_stats.loc['std', 'aspect_ratio']} | {summary_stats.loc['std', 'file_size_kb']} |

*A complete list including failed images is available in `{args.output_csv}`.*

## 3. Current Model Detection Results (DocLayNet)
The current pipeline uses a pre-trained DocLayNet YOLO model. It is important to distinguish between what the model outputs and what we structurally expect from legal documents:
- The model outputs based on **11 pre-defined classes** (Caption, Footnote, Formula, List-item, Page-footer, Page-header, Picture, Section-header, Table, Text, Title).
- On our specific dataset of Vietnamese legal documents, **the vast majority of detections are classified simply as `Text`**. 
- The model does **not** differentiate between fine-grained legal sections such as Articles, Paragraphs, Lists, or Signatures.
- While it successfully bounds regions containing text, it acts more as a general region detector than a semantic legal document parser.

## 4. Manually Observed Layout Components (for future labeling)
Through human visual inspection of sample images, Vietnamese legal documents typically follow strict structural guidelines (e.g., Circular No. 01/2011/TT-BNV). The following layout components are structurally present in the images:

- **Headers:** Located at the top, usually containing the National Motto ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM") and the Issuing Authority.
- **Titles:** Bold, centered text identifying the document type and subject (e.g., "QUYẾT ĐỊNH", "NGHỊ ĐỊNH").
- **Articles:** Structural blocks beginning with "Điều 1.", "Điều 2.", etc.
- **Paragraphs:** Standard body text containing legal provisions.
- **Lists:** Bulleted or enumerated items (e.g., `a)`, `b)`, `1.`, `2.`, `-`).
- **Tables:** Tabular data, often used in appendices or specific regulations.
- **Signatures:** Found at the end of the document, containing stamps, dates, and signee titles (e.g., "CHỦ TỊCH", "TM. CHÍNH PHỦ").
- **Footers:** Contains page numbers or recipient tracking info ("Nơi nhận:").

## 5. Recommendations for Labeling & Future Models
To build a highly accurate, legal-domain-specific model that parses exact document structure, we propose moving away from the 11 generic DocLayNet classes. Instead, we recommend using the following **8 classes**:

1. `header`
2. `title`
3. `article`
4. `paragraph`
5. `list`
6. `table`
7. `signature`
8. `footer`

**Next Steps:** Achieving this fine-grained legal taxonomy will require manually annotating a representative subset of the dataset (e.g., 200–300 images) using these 8 custom classes and then fine-tuning the YOLO model on this custom dataset.
"""
    
    with open(args.output_report, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"Saved EDA report to {args.output_report}")
    print("\nEDA Completed Successfully.")

if __name__ == "__main__":
    main()
