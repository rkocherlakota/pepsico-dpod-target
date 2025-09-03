# PepsiCo DPOD Target - Document Processing with Object Detection and OCR

A comprehensive document processing application that combines Object Detection (YOLOX) and OCR (Google Cloud Vision) to extract structured information from receipts and invoices.

## 🚀 Features

- **Object Detection**: YOLOX model trained to detect:
  - `sticker` - Receipt stickers with dates
  - `signature` - Customer signatures
  - `receipt_outline` - Receipt boundaries
  - `bad` - Poor quality images

- **OCR Processing**: Google Cloud Vision API integration for text extraction
- **Batch Processing**: Handle multiple PDF files simultaneously
- **Excel Output**: Structured results in Excel format with exactly 12 fields
- **Web Interface**: User-friendly Flask web application
- **Real-time Processing**: Live feedback and progress tracking

## 📋 Required Excel Output Fields

The application generates Excel files with exactly these 12 fields:
1. `filename` - Name of the processed file
2. `invoice_number` - Extracted invoice number
3. `store_number` - Extracted store number
4. `invoice_date` - Extracted invoice date (MM/DD/YYYY format)
5. `sticker_date` - Extracted sticker date or "Not Available"
6. `total_quantity` - Extracted total quantity
7. `has_frito_lay` - Whether Frito Lay was found (Yes/No)
8. `has_signature` - Whether signature was detected (Yes/No)
9. `has_sticker` - Whether sticker was detected by OD model (Yes/No)
10. `is_valid` - Document validity based on sticker presence
11. `processing_status` - Processing success/failure status
12. `error_message` - Any error messages

## 🛠️ Installation

### Prerequisites

- Python 3.10+
- Google Cloud Vision API credentials
- YOLOX model checkpoint file

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/rkocherlakota/pepsico-dpod-target.git
   cd pepsico-dpod-target
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv_py310
   source venv_py310/bin/activate  # On Windows: venv_py310\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Google Cloud credentials**
   - Place your `global-lexicon-271715-bbd471224971_PROD.json` file in the root directory
   - Set environment variable: `export GOOGLE_APPLICATION_CREDENTIALS="global-lexicon-271715-bbd471224971_PROD.json"`

5. **Download YOLOX model checkpoint**
   - Place `last_mosaic_epoch_ckpt_100eps.pth` in the root directory
   - This is the trained model for detecting stickers, signatures, etc.

## 🚀 Running the Application

### Start the Flask Server
```bash
source venv_py310/bin/activate
python app.py
```

The application will be available at: http://localhost:8080

### Usage

1. **Single File Processing**
   - Select "Single File" mode
   - Upload a PDF file
   - View results in table format with summary statistics

2. **Batch Processing**
   - Select "Multiple Files" mode
   - Upload multiple PDF files
   - Process all files simultaneously
   - View consolidated results in Excel format

## 📁 Project Structure

```
pepsico-dpod-target/
├── app.py                          # Main Flask application
├── models.py                       # Pydantic data models
├── ocr_preprocessor.py            # OCR processing logic
├── batch_processor.py             # Batch processing logic
├── config.py                      # Configuration settings
├── requirements.txt                # Python dependencies
├── templates/
│   └── index.html                 # Web interface
├── yolox_od/                      # YOLOX Object Detection
│   ├── inference.py               # OD model inference
│   ├── exps/                      # YOLOX experiments
│   ├── yolox/                     # YOLOX core modules
│   └── tools/                     # YOLOX tools
├── uploads/                       # Temporary upload storage
├── inference_output/              # Excel output files
└── global-lexicon-*.json         # Google Cloud credentials
```

## 🔧 Configuration

### Model Settings
- **YOLOX Model**: Configured in `yolox_od/config.py`
- **Confidence Threshold**: 0.25 (adjustable in `yolox_od/inference.py`)
- **NMS Threshold**: 0.65 (adjustable in `yolox_od/inference.py`)

### OCR Settings
- **DPI**: 200 (for PDF to image conversion)
- **Date Format**: MM/DD/YYYY (automatically converted from various formats)
- **Text Patterns**: Optimized for receipt/invoice extraction

## 📊 Output Examples

### Successful Processing
- **File**: `37338500.pdf`
- **OD Results**: Sticker detected, Signature detected
- **OCR Results**: Invoice number, store number, dates, quantities
- **Excel Row**: All fields populated, `is_valid = "Valid"`

### No Sticker Detected
- **File**: `4306447.pdf`
- **OD Results**: No sticker, Signature detected
- **OCR Results**: Invoice number, store number, dates, quantities
- **Excel Row**: `sticker_date = "Not Available"`, `is_valid = "Invalid"`

## 🐛 Troubleshooting

### Common Issues

1. **Google Cloud Credentials**
   - Ensure `global-lexicon-*.json` is in the root directory
   - Check environment variable is set correctly

2. **YOLOX Model**
   - Verify `last_mosaic_epoch_ckpt_100eps.pth` exists
   - Check model file permissions

3. **Dependencies**
   - Ensure all packages in `requirements.txt` are installed
   - Check Python version compatibility

### Debug Logging

The application includes comprehensive logging:
- OD model detection results
- OCR processing steps
- Excel row creation
- Error handling and fallbacks

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the debug logs
3. Open an issue on GitHub

## 🎯 Performance

- **Processing Speed**: ~2-5 seconds per PDF page
- **Accuracy**: High accuracy for sticker/signature detection
- **Scalability**: Handles multiple files efficiently
- **Memory Usage**: Optimized for production deployment

---

**Note**: This application is specifically designed for PepsiCo document processing workflows and includes custom-trained models for receipt analysis.
