# Pepsico Document OCR Extractor

A Flask web application that extracts key information from Pepsico documents using Google Cloud Vision OCR.

## Features

- Upload PDF or image files (JPG, PNG)
- Automatic PDF to image conversion using Poppler
- Google Cloud Vision OCR text extraction
- Extracts key document fields:
  - Invoice Number
  - Store Number
  - Invoice Date
  - Sticker Date
  - Total Quantity
  - Frito Lay presence
  - Signature presence
- Results saved to Excel file
- Web-based interface

## Prerequisites

- Python 3.9+
- Google Cloud Vision API credentials
- Poppler (for PDF processing)

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd pepsico_ocr
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv target_dpod
   source target_dpod/bin/activate  # On Windows: target_dpod\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Poppler**
   - **macOS**: `brew install poppler`
   - **Ubuntu/Debian**: `sudo apt install poppler-utils`
   - **Windows**: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/) and set `POPPLER_PATH` environment variable

5. **Set up Google Cloud Vision credentials**
   - Create a Google Cloud project
   - Enable the Vision API
   - Create a service account and download the JSON credentials file
   - Place the credentials file in the project root and update `config.py` with the filename

## Configuration

Update `config.py` with your Google Cloud credentials filename:

```python
SERVICE_ACCOUNT_PATH = "your-credentials-file.json"
```

## Usage

1. **Start the application**
   ```bash
   source target_dpod/bin/activate
   python3 app.py
   ```

2. **Access the web interface**
   - Open your browser and go to: http://localhost:8080

3. **Upload documents**
   - Click "Choose File" and select a PDF or image file
   - Click "Process Document"
   - View the extracted information

## API Endpoints

- `GET /` - Home page with upload interface
- `POST /upload` - Basic file upload endpoint
- `POST /upload-document` - OCR processing endpoint

## File Structure

```
pepsico_ocr/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── ocr_preprocessor.py    # OCR processing logic
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface
├── uploads/              # Uploaded files (auto-created)
├── inference_output/     # OCR results (auto-created)
└── annotated_images/     # Processed images (auto-created)
```

## Environment Variables

- `UPLOAD_DIR` - Directory for uploaded files (default: `./uploads`)
- `PDF_DPI` - DPI for PDF conversion (default: 200)
- `PDF_MAX_PAGES` - Maximum pages to process from PDF
- `POPPLER_PATH` - Path to Poppler executables (Windows only)

## Security Notes

- The Google Cloud credentials JSON file is excluded from version control
- Uploaded files are stored temporarily and cleaned up
- The application runs in debug mode for development

## Troubleshooting

### Port already in use
If port 8080 is in use, modify the port in `app.py`:
```python
app.run(host="0.0.0.0", port=8081, debug=True)
```

### Poppler not found
- Ensure Poppler is installed and in your PATH
- On Windows, set the `POPPLER_PATH` environment variable

### Google Cloud Vision errors
- Verify your credentials file is correct
- Ensure the Vision API is enabled in your Google Cloud project
- Check that your service account has the necessary permissions
