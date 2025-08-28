from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


class InvoiceFields(BaseModel):
    """Model for extracted invoice fields from OCR"""
    invoice_number: Optional[int] = Field(None, description="Extracted invoice number")
    store_number: Optional[int] = Field(None, description="Extracted store number")
    invoice_date: Optional[str] = Field(None, description="Extracted invoice date")
    sticker_date: Optional[str] = Field(None, description="Extracted sticker date")
    total_quantity: Optional[float] = Field(None, description="Extracted total quantity")
    has_frito_lay: bool = Field(False, description="Whether Frito Lay was found")
    has_signature: bool = Field(False, description="Whether signature was found")

    @validator('invoice_number', 'store_number', pre=True)
    def validate_and_convert_to_integer(cls, v):
        """Convert string to integer for invoice and store numbers"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        if isinstance(v, str):
            # Remove any non-digit characters except hyphens, then remove hyphens
            cleaned = re.sub(r'[^0-9\-]', '', v)
            cleaned = cleaned.replace('-', '')  # Remove hyphens
            if cleaned:
                try:
                    return int(cleaned)
                except ValueError:
                    pass
        elif isinstance(v, int):
            return v
        return None

    @validator('invoice_date', 'sticker_date')
    def validate_date_fields(cls, v): 
        """Validate date format"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            
            # Basic date validation - check if it looks like a date
            date_patterns = [
                r'\d{1,2}[\.\-/\s](?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\.\-/\s](?:20)?\d{2}',
                r'\d{1,2}[\-/\.]\d{1,2}[\-/\.](?:20)?\d{2}',
                r'\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}'
            ]
            
            is_valid_date = any(re.search(pattern, v, re.IGNORECASE) for pattern in date_patterns)
            if not is_valid_date:
                return None
            return v
        return v

    @validator('total_quantity')
    def validate_quantity(cls, v):
        """Validate quantity is a positive number"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                v_float = float(v)
                if v_float < 0:
                    return None
                return v_float
            except ValueError:
                return None
        elif isinstance(v, (int, float)):
            if v < 0:
                return None
            return float(v)
        return None


class PageResult(BaseModel):
    """Model for individual page processing results"""
    page: int = Field(..., description="Page number")
    page_fields: InvoiceFields = Field(..., description="Fields extracted from this page")
    updates_applied: Dict[str, str] = Field(..., description="Which fields were updated from this page")





class OCRResult(BaseModel):
    """Model for complete OCR processing result"""
    filename: str = Field(..., description="Name of the processed file")
    total_pages: int = Field(..., description="Total number of pages processed")
    master_fields: InvoiceFields = Field(..., description="Combined fields from all pages")
    fields_found: List[str] = Field(..., description="List of fields that were successfully extracted")
    page_details: List[PageResult] = Field(..., description="Detailed results for each page")
    processing_status: str = Field("Success", description="Processing status")
    error_message: str = Field("", description="Error message if processing failed")

    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename is not empty and has valid characters"""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        # Check for potentially dangerous characters
        if any(char in v for char in ['<', '>', ':', '"', '|', '?', '*']):
            raise ValueError(f"Filename contains invalid characters: {v}")
        return v.strip()

    @validator('total_pages')
    def validate_total_pages(cls, v):
        """Validate total pages is positive"""
        if v < 0:
            raise ValueError(f"Total pages cannot be negative: {v}")
        return v

    @validator('processing_status')
    def validate_status(cls, v):
        """Validate processing status"""
        allowed_statuses = ['Success', 'Failed', 'Partial']
        if v not in allowed_statuses:
            raise ValueError(f"Invalid processing status. Must be one of: {allowed_statuses}")
        return v


class ExcelRow(BaseModel):
    """Model for a single row in the Excel output"""
    filename: str = Field(..., description="Name of the processed file")
    invoice_number: Optional[int] = Field(None, description="Extracted invoice number")
    store_number: Optional[int] = Field(None, description="Extracted store number")
    invoice_date: Optional[str] = Field(None, description="Extracted invoice date")
    sticker_date: Optional[str] = Field(None, description="Extracted sticker date")
    total_quantity: Optional[float] = Field(None, description="Extracted total quantity")
    has_frito_lay: bool = Field(False, description="Whether Frito Lay was found")
    has_signature: bool = Field(False, description="Whether signature was found")
    has_sticker: bool = Field(False, description="Whether sticker date was found")
    is_valid: str = Field("Invalid", description="Document validity (Valid/Invalid)")
    processing_status: str = Field("Success", description="Processing status")
    error_message: str = Field("", description="Error message if processing failed")
    process_type: str = Field("Single", description="Type of processing (Single/Multiple/Folder)")
    start_time: Optional[str] = Field(None, description="Processing start timestamp")
    end_time: Optional[str] = Field(None, description="Processing end timestamp")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")

    @validator('has_frito_lay', 'has_signature', 'has_sticker', pre=True)
    def ensure_boolean_values(cls, v):
        """Ensure boolean values are True/False, not 1/0 or TRUE/FALSE"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return False
        
        if isinstance(v, str):
            v = v.upper().strip()
            if v in ['TRUE', '1', 'YES', 'Y']:
                return True
            elif v in ['FALSE', '0', 'NO', 'N']:
                return False
            else:
                return False
        elif isinstance(v, bool):
            return v
        elif isinstance(v, int):
            return bool(v)
        return False

    @validator('is_valid', pre=True)
    def ensure_validity_values(cls, v):
        """Ensure is_valid values are 'Valid'/'Invalid', not True/False or 1/0"""
        if v is None or v == "":
            return 'Invalid'
        
        if isinstance(v, str):
            v = v.lower().strip()
            if v in ['true', '1', 'yes', 'y', 'valid']:
                return 'Valid'
            elif v in ['false', '0', 'no', 'n', 'invalid']:
                return 'Invalid'
            else:
                return 'Invalid'
        elif isinstance(v, bool):
            return 'Valid' if v else 'Invalid'
        elif isinstance(v, int):
            return 'Valid' if v else 'Invalid'
        return 'Invalid'

    @classmethod
    def from_ocr_result(cls, ocr_result: OCRResult, process_type: str = "Single", 
                       start_time: str = None, end_time: str = None, 
                       processing_time: float = None) -> 'ExcelRow':
        """Create ExcelRow from OCRResult"""
        master_fields = ocr_result.master_fields
        
        # Determine has_sticker value
        has_sticker = master_fields.sticker_date is not None
        
        # Determine is_valid value
        if (master_fields.sticker_date is not None and 
            master_fields.has_signature):
            is_valid = "Valid"
        else:
            is_valid = "Invalid"
        

        
        return cls(
            filename=ocr_result.filename,
            invoice_number=master_fields.invoice_number,
            store_number=master_fields.store_number,
            invoice_date=master_fields.invoice_date,
            sticker_date=master_fields.sticker_date,
            total_quantity=master_fields.total_quantity,
            has_frito_lay=master_fields.has_frito_lay,
            has_signature=master_fields.has_signature,
            has_sticker=has_sticker,
            is_valid=is_valid,
            processing_status=ocr_result.processing_status,
            error_message=ocr_result.error_message,
            process_type=process_type,
            start_time=start_time,
            end_time=end_time,
            processing_time=processing_time
        )

    @classmethod
    def from_failed_processing(cls, filename: str, error_message: str, 
                              process_type: str = "Single", start_time: str = None, 
                              end_time: str = None, processing_time: float = None) -> 'ExcelRow':
        """Create ExcelRow for failed processing"""
        return cls(
            filename=filename,
            processing_status="Failed",
            error_message=error_message,
            process_type=process_type,
            start_time=start_time,
            end_time=end_time,
            processing_time=processing_time
        )


class BatchProcessingResult(BaseModel):
    """Model for batch processing summary"""
    total_files: int = Field(..., description="Total number of files processed")
    successful: int = Field(..., description="Number of successfully processed files")
    failed: int = Field(..., description="Number of failed files")
    output_file: str = Field(..., description="Path to output Excel file")
    processing_time: Optional[float] = Field(None, description="Total processing time in seconds")
    results: List[ExcelRow] = Field(..., description="List of all processing results")

    @validator('total_files', 'successful', 'failed')
    def validate_counts(cls, v):
        """Validate count fields are non-negative"""
        if v < 0:
            raise ValueError(f"Count cannot be negative: {v}")
        return v

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.successful / self.total_files) * 100
