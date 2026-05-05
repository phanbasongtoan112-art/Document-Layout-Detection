# Exploratory Data Analysis (EDA) Report
**Project:** Vietnamese Legal Document Layout Detection  
**Dataset:** PNG Images from VBPL PDFs  

## 1. Dataset Overview
- **Total Images Scanned:** 1673
- **Successfully Read:** 1672
- **Failed to Read:** 1 (Detailed errors in `eda_image_stats.csv`)
- **Samples Extracted:** 10 (located in `eda_samples/`)

## 2. Image Statistics Summary
The following table summarizes the dimensions and file sizes of the successfully read images:

| Statistic | Width (px) | Height (px) | Aspect Ratio | File Size (KB) |
| :--- | :--- | :--- | :--- | :--- |
| **Minimum** | 1637.0 | 1653.0 | 0.7 | 0.0 |
| **Maximum** | 2339.0 | 2339.0 | 1.42 | 3160.27 |
| **Mean** | 2152.94 | 1833.87 | 1.22 | 492.72 |
| **Std Dev** | 301.83 | 294.69 | 0.31 | 427.52 |

*A complete list including failed images is available in `eda_image_stats.csv`.*

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
