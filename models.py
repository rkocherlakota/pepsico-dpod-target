from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import re


class InvoiceFields(BaseModel):
    """Model for extracted invoice fields from OCR"""
    invoice_number: Optional[int] = Field(None, description="Extracted invoice number")
    store_number: Optional[int] = Field(None, description="Extracted store number")
    invoice_date: Optional[str] = Field(None, description="Extracted invoice date")
    sticker_date: Optional[str] = Field(None, description="Extracted sticker date")
    total_quantity: Optional[Union[float, str]] = Field(None, description="Extracted total quantity")
    has_frito_lay: bool = Field(False, description="Whether Frito Lay was found")
    has_signature: bool = Field(False, description="Whether signature was found")
    has_sticker: bool = Field(False, description="Whether sticker was detected")
    is_valid: str = Field("Invalid", description="Whether the document is valid or invalid")

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
        """Validate quantity is a valid number (including negative) or preserve special values like 'N/A'"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            # Check if it's a special value like 'N/A', 'NA', etc.
            if v.upper() in ['N/A', 'NA', 'NONE', 'NOT AVAILABLE']:
                return v  # Preserve the original string value
            
            # Try to convert to float for numeric validation
            try:
                v_float = float(v)
                # Convert negative numbers to absolute values
                v_float = abs(v_float)
                return v_float
            except ValueError:
                return None
        elif isinstance(v, (int, float)):
            # Convert negative numbers to absolute values
            v = abs(v)
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
    sticker_flag: Optional[bool] = Field(None, description="Sticker detection flag from Object Detection model")
    signature_flag: Optional[bool] = Field(None, description="Signature detection flag from Object Detection model")


class ExcelRow(BaseModel):
    """Model for Excel output row - only contains the exact fields specified"""
    filename: str = Field(..., description="Name of the processed file")
    invoice_number: Optional[int] = Field(None, description="Extracted invoice number")
    store_number: Optional[int] = Field(None, description="Extracted store number")
    invoice_date: Optional[str] = Field(None, description="Extracted invoice date")
    sticker_date: Optional[str] = Field(None, description="Extracted sticker date")
    total_quantity: Optional[Union[float, str]] = Field(None, description="Extracted total quantity")
    has_frito_lay: bool = Field(False, description="Whether Frito Lay was found")
    has_signature: bool = Field(False, description="Whether signature was found")
    has_sticker: bool = Field(False, description="Whether sticker was detected (from OD model)")
    is_valid: str = Field("Invalid", description="Whether the document is valid or invalid")
    processing_status: str = Field("Success", description="Processing status")
    error_message: str = Field("", description="Error message if processing failed")

    @classmethod
    def from_ocr_result(cls, result: OCRResult, sticker_flag: bool):
        """Create ExcelRow from OCRResult"""
        return cls(
            filename=result.filename,
            invoice_number=result.master_fields.invoice_number,
            store_number=result.master_fields.store_number,
            invoice_date=result.master_fields.invoice_date,
            sticker_date=result.master_fields.sticker_date,
            total_quantity=result.master_fields.total_quantity,
            has_frito_lay=result.master_fields.has_frito_lay,
            has_signature=result.master_fields.has_signature,
            has_sticker=sticker_flag,  # Use the sticker_flag from OD model
            is_valid=result.master_fields.is_valid,
            processing_status=result.processing_status,
            error_message=result.error_message
        )

    @classmethod
    def from_failed_processing(cls, filename: str, error_message: str):
        """Create ExcelRow for failed processing"""
        return cls(
            filename=filename,
            invoice_number=None,
            store_number=None,
            invoice_date=None,
            sticker_date=None,
            total_quantity=None,
            has_frito_lay=False,
            has_signature=False,
            has_sticker=False,
            is_valid="Invalid",
            processing_status="Failed",
            error_message=error_message
        )


class BatchProcessingResult(BaseModel):
    """Model for batch processing results"""
    successful: int = Field(..., description="Number of successfully processed files")
    failed: int = Field(..., description="Number of failed files")
    total_files: int = Field(..., description="Total number of files processed")
    output_file: str = Field(..., description="Path to output Excel file")
    results: List[Dict[str, Any]] = Field(..., description="Detailed results for each file")
