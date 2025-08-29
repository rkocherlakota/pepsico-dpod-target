# DPOD - Target

A Flask web application that validates delivery receipts by extracting key information using Google Cloud Vision OCR. Supports both single receipt processing and batch processing of multiple PDF files.

## Features

- **Single Receipt Processing**: Upload individual delivery receipt files (PDF, JPG, PNG)
- **Batch Processing**: Process multiple delivery receipts from a folder at once
- **Automatic PDF to image conversion** using Poppler
- **Google Cloud Vision OCR** text extraction
- **Excel Output**: Results automatically saved to Excel files with structured data
- **Data Validation**: Pydantic models ensure data integrity and consistency
- **Progress Tracking**: Real-time progress updates during batch processing
- **Error Handling**: Comprehensive error handling with validation feedback

### Extracted Fields

- Invoice Number
- Store Number
- Invoice Date
- Sticker Date
- Total Quantity
- Frito Lay presence
- Signature presence
- Receipt validity

## Prerequisites

- Python 3.9+
- Google Cloud Vision API credentials
- Poppler (for PDF processing)

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd dpod-target
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

### Method 1: Web Interface (Single Receipt)

1. **Start the application**
   ```bash
   source target_dpod/bin/activate
   python3 app.py
   ```

2. **Access the web interface**
   - Open your browser and go to: http://localhost:8080

3. **Upload delivery receipts**
   - Select "Single Receipt" from the dropdown
   - Choose a PDF or image file
   - Click "Validate Single Receipt"
   - View the validation results

### Method 2: Web Interface (Batch Processing)

1. Start the Flask application as above
2. Use the "Batch Processing" section:
   - Select "Multiple Receipts" or "Process Folder" from the dropdown
   - Choose files or enter folder path containing your delivery receipt PDFs
   - Click "Validate Multiple Receipts" or "Process Folder"
   - Wait for processing to complete
   - Results will be saved to `inference_output/batch_ocr_results.xlsx`

### Method 3: Command Line Interface (Batch Processing)

Use the standalone batch processor script for delivery receipts:

```bash
python3 batch_processor.py /path/to/pdf/folder
```

**Options:**
- `--output` or `-o`: Specify custom output Excel file path
- `--dpi`: Set PDF conversion DPI (default: 200)
- `--max-pages`: Limit pages per PDF

**Examples:**
```bash
# Basic usage
python3 batch_processor.py /Users/username/Documents/pdfs

# With custom output file
python3 batch_processor.py /Users/username/Documents/pdfs --output results.xlsx

# With custom DPI and page limit
python3 batch_processor.py /Users/username/Documents/pdfs --dpi 300 --max-pages 5
```

## Output Format

The Excel file contains the following columns:

| Column | Description |
|--------|-------------|
| filename | Name of the processed PDF file |
| invoice_number | Extracted invoice number (integer) |
| store_number | Extracted store number (integer) |
| invoice_date | Extracted invoice date (string) |
| sticker_date | Extracted sticker date (string) |
| total_quantity | Extracted total quantity (float) |
| has_frito_lay | Whether "Frito Lay" was found (True/False) |
| has_signature | Whether signature was found (True/False) |
| has_sticker | Whether sticker date was found (True/False) |
| is_valid | Document validity (Valid/Invalid) |
| processing_status | Success/Failed status |
| error_message | Error details if processing failed |

## Data Validation

The application uses Pydantic models to validate all data before writing to Excel:

### Validation Rules

- **Invoice/Store Numbers**: Must be valid integers (extracted from text and converted)
- **Dates**: Must match common date formats (DD/MM/YYYY, MM/DD/YYYY, etc.)
- **Quantities**: Must be positive numbers (float)
- **Boolean Values**: Must be True/False (converts from TRUE/FALSE, 1/0, YES/NO, etc.)
- **Document Validity**: Must be "Valid"/"Invalid" (converts from True/False, 1/0, etc.)
- **Filenames**: Must not contain dangerous characters
- **Processing Status**: Must be one of: Success, Failed, Partial

## API Endpoints

- `GET /` - Home page with upload interface
- `POST /upload` - Basic file upload endpoint
- `POST /upload-document` - OCR processing endpoint
- `POST /batch-process` - Batch processing endpoint

## File Structure

```
pepsico_ocr/
├── app.py                 # Main Flask application
├── batch_processor.py     # Standalone batch processor
├── config.py              # Configuration settings
├── ocr_preprocessor.py    # OCR processing logic
├── models.py              # Pydantic data models and validation
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface
├── uploads/              # Uploaded files (auto-created)
├── inference_output/     # OCR results (auto-created)
│   ├── ocr_results.xlsx  # Single document results
│   └── batch_ocr_results.xlsx  # Batch processing results
└── annotated_images/     # Processed images (auto-created)
```

## Environment Variables

- `UPLOAD_DIR` - Directory for uploaded files (default: `./uploads`)
- `PDF_DPI` - DPI for PDF conversion (default: 200)
- `PDF_MAX_PAGES` - Maximum pages to process from PDF
- `POPPLER_PATH` - Path to Poppler executables (Windows only)

## Troubleshooting

### Common Issues

1. **Port already in use**
   If port 8080 is in use, modify the port in `app.py`:
   ```python
   app.run(host="0.0.0.0", port=8081, debug=True)
   ```

2. **Poppler not found**
   - Ensure Poppler is installed and in your PATH
   - On Windows, set the `POPPLER_PATH` environment variable

3. **Google Cloud Vision errors**
   - Verify your credentials file is correct
   - Ensure the Vision API is enabled in your Google Cloud project
   - Check that your service account has the necessary permissions

4. **"No PDF files found"**
   - Ensure the folder path is correct and contains PDF files

5. **PDF conversion errors**
   - Install Poppler utilities (see Installation section)

6. **Permission errors**
   - Ensure the application has read access to the input folder and write access to the output directory

7. **Validation errors**
   - Check the console output for specific validation failures

### Performance Tips

- For large batches, consider processing in smaller chunks
- Higher DPI settings improve accuracy but increase processing time
- The application processes files sequentially to avoid overwhelming the OCR service

## Security Notes

- The Google Cloud credentials JSON file is excluded from version control
- Uploaded files are stored temporarily and cleaned up
- The application runs in debug mode for development
- The batch processor processes files from the local filesystem
- Ensure the input folder contains only trusted PDF files
- Temporary files are automatically cleaned up after processing
