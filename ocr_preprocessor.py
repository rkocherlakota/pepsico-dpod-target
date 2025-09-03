# ocr_processor.py

from google.cloud import vision
from google.oauth2 import service_account
import re
import cv2
import numpy as np
import io
import os
import pandas as pd
from datetime import datetime
import openpyxl
from openpyxl.styles import Alignment
from pathlib import Path
from config import SERVICE_ACCOUNT_PATH, INFERENCE_OUTPUT_DIR
from models import InvoiceFields, PageResult, OCRResult, ExcelRow

# Initialize client with credentials
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

class OCRProcessor:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient(credentials=credentials)

    def extract_invoice_fields(self, full_text: str, signature_flag: bool, has_sticker: bool = False, is_valid: str = "Invalid") -> InvoiceFields:
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        def first_match(patterns, text, flags=re.IGNORECASE):
            for p in patterns:
                m = re.search(p, text, flags)
                if m:
                    return m.group(1) if m.lastindex else m.group(0)
            return None

        # Improved invoice number patterns - more specific to avoid false matches
        invoice_patterns = [
            r"\bDOCUMENT\s*(?:NO\.?|#|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]+)\b",  # Document first
            r"\bINVOICE\s*(?:NO\.?|#|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]+)\b(?!\s+DATE)",  # Avoid matching "Invoice Date"
            r"\bINV\s*(?:NO\.?|#)?\s*[:\-]?\s*([A-Z0-9\-]+)\b",
        ]
        invoice_number = first_match(invoice_patterns, full_text)

        # Store patterns - only match "Store Number: 2516" format
        store_patterns = [
            r"\bSTORE\s*(?:NUMBER|NO\.?)\s*[:\-]?\s*([A-Z0-9\-]{2,})\b",
        ]
        store_number = first_match(store_patterns, full_text)

        # Improved date patterns - prioritize MM/DD/YYYY format
        invoice_date_patterns = [
            r"\b(?:0?[1-9]|1[0-2])[/\-\.](?:0?[1-9]|[12][0-9]|3[01])[/\-\.](?:20)?\d{2}\b",  # MM/DD/YYYY
            r"\b(?:0?[1-9]|[12][0-9]|3[01])[\.\-/\s](?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\.\-/\s](?:20)?\d{2}\b",  # DD/MMM/YYYY
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?:0?[1-9]|[12][0-9]|3[01]),?\s+(?:20)?\d{2}\b",  # MMM DD, YYYY
            r"\b(?:20)?\d{2}[/\-\.](?:0?[1-9]|1[0-2])[/\-\.](?:0?[1-9]|[12][0-9]|3[01])\b",  # YYYY/MM/DD
        ]
        
        invoice_date = None
        for pattern in invoice_date_patterns:
            match = re.search(pattern, full_text, flags=re.IGNORECASE)
            if match:
                invoice_date = match.group(0)
                # Convert DD.MMM.YYYY format to MM/DD/YYYY format
                invoice_date = self._convert_date_format(invoice_date)
                break

        # Enhanced sticker date pattern to match the same formats as invoice_date
        # Only extract sticker date if OD model detected a sticker
        sticker_date = None
        if has_sticker:
            sticker_date_patterns = [
                r"\b(?:0?[1-9]|1[0-2])[/\-\.](?:0?[1-9]|[12][0-9]|3[01])[/\-\.](?:20)?\d{2}\b",  # MM/DD/YYYY
                r"\b(?:0?[1-9]|[12][0-9]|3[01])[\.\-/\s](?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\.\-/\s](?:20)?\d{2}\b",  # DD/MMM/YYYY
                r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?:0?[1-9]|[12][0-9]|3[01]),?\s+(?:20)?\d{2}\b",  # MMM DD, YYYY
                r"\b(?:20)?\d{2}[/\-\.](?:0?[1-9]|1[0-2])[/\-\.](?:0?[1-9]|[12][0-9]|3[01])\b",  # YYYY/MM/DD
            ]
            
            for pattern in sticker_date_patterns:
                match = re.search(pattern, full_text, flags=re.IGNORECASE)
                if match:
                    sticker_date = match.group(0)
                    # Convert sticker date format as well
                    sticker_date = self._convert_date_format(sticker_date)
                    break

        # Improved quantity patterns
        total_qty = None
        total_qty_patterns = [
            r"\bTOTAL\s*(?:QTY|QUANTITY)\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",
            r"\b(?:QTY|QUANTITY)\s*TOTAL\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",
            r"\bTOTAL\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\s*(?:QTY|QUANTITY)\b",
            r"\bTOTAL\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",
            r"\b(?:QTY|QUANTITY)\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",
            r"\bAMOUNT\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",
            r"\bTOTAL\s*EACHES\s*SOLD\s*[:\-]?\s*([-]?[0-9,]+(?:\.[0-9]+)?)\b",  # Handle "TOTAL EACHES SOLD: 80"
        ]
        
        # First try to find quantity in lines containing quantity keywords
        for line in lines:
            if re.search(r"\b(QTY|QUANTITY|TOTAL|AMOUNT)\b", line, re.IGNORECASE):
                candidate = first_match(total_qty_patterns, line)
                if candidate:
                    try:
                        # Remove commas and convert to float
                        total_qty = float(candidate.replace(',', ''))
                        break
                    except ValueError:
                        continue

        # If no quantity found in specific lines, search the entire text
        if total_qty is None:
            candidate = first_match(total_qty_patterns, full_text)
            if candidate:
                try:
                    total_qty = float(candidate.replace(',', ''))
                except ValueError:
                    pass

        # Check for Frito-Lay presence
        has_frito_lay = bool(re.search(r"\bFRITO\s*LAY\b", full_text, re.IGNORECASE))

        # Check for signature presence (from OCR text)
        has_signature = signature_flag

        # Check for sticker presence (from OD model)
        has_sticker = has_sticker

        # Determine validity based on sticker presence
        is_valid = "Valid" if has_sticker else "Invalid"

        return InvoiceFields(
            invoice_number=invoice_number,
            store_number=store_number,
            invoice_date=invoice_date,
            sticker_date=sticker_date,
            total_quantity=total_qty,
            has_frito_lay=has_frito_lay,
            has_signature=has_signature,
            has_sticker=has_sticker,
            is_valid=is_valid
        )

    def _convert_date_format(self, date_str: str) -> str:
        """Convert various date formats to MM/DD/YYYY"""
        if not date_str:
            return date_str

        # Handle DD.MMM.YYYY format (e.g., "04.Jul.2025")
        dd_mmm_yyyy_pattern = r"(\d{1,2})\.(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.(\d{4})"
        match = re.match(dd_mmm_yyyy_pattern, date_str, re.IGNORECASE)
        if match:
            day, month, year = match.groups()
            month_num = self._month_to_number(month)
            print(f"DD.MMM.YYYY pattern matched: day={day}, month={month}, year={year}")
            result = f"{month_num:02d}/{int(day):02d}/{year}"
            print(f"DD.MMM.YYYY conversion result: {result}")
            return result

        # Handle MM/DD/YYYY format
        mm_dd_yyyy_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        match = re.match(mm_dd_yyyy_pattern, date_str)
        if match:
            month, day, year = match.groups()
            # Check if this might actually be DD/MM/YYYY
            if int(month) > 12 and int(day) <= 12:
                # This is likely DD/MM/YYYY, convert to MM/DD/YYYY
                result = f"{int(day):02d}/{int(month):02d}/{year}"
            else:
                # This is MM/DD/YYYY, ensure two-digit format
                result = f"{int(month):02d}/{int(day):02d}/{year}"
            print(f"MM/DD/YYYY pattern matched: month={month}, day={day}, year={year}")
            print(f"MM/DD/YYYY formatting result: {result}")
            return result

        # Handle DD/MM/YYYY format
        dd_mm_yyyy_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        match = re.match(dd_mm_yyyy_pattern, date_str)
        if match:
            day, month, year = match.groups()
            # Check if this might actually be MM/DD/YYYY
            if int(day) > 12 and int(month) <= 12:
                # This is likely MM/DD/YYYY, convert to DD/MM/YYYY
                result = f"{int(month):02d}/{int(day):02d}/{year}"
            else:
                # This is DD/MM/YYYY, convert to MM/DD/YYYY
                result = f"{int(month):02d}/{int(day):02d}/{year}"
            print(f"DD/MM/YYYY pattern matched: day={day}, month={month}, year={year}")
            print(f"DD/MM/YYYY formatting result: {result}")
            return result

        # Handle YYYY-MM-DD format
        yyyy_mm_dd_pattern = r"(\d{4})-(\d{1,2})-(\d{1,2})"
        match = re.match(yyyy_mm_dd_pattern, date_str)
        if match:
            year, month, day = match.groups()
            result = f"{int(month):02d}/{int(day):02d}/{year}"
            print(f"YYYY-MM-DD pattern matched: year={year}, month={month}, day={day}")
            print(f"YYYY-MM-DD formatting result: {result}")
            return result

        # If no pattern matches, return as is
        print(f"Date conversion: {date_str} -> {date_str}")
        return date_str

    def _month_to_number(self, month: str) -> int:
        """Convert month name to number"""
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return month_map.get(month.lower(), 1)

    def process_images(self, image_paths: list, filename: str, sticker_flag: bool = False, signature_flag: bool = False) -> OCRResult:
        """Process multiple images and return combined results"""
        print(f"process_images called with {len(image_paths)} images, filename: {filename}, sticker_flag: {sticker_flag}, signature_flag: {signature_flag}")
        all_fields = []
        page_results = []
        
        for i, image_path in enumerate(image_paths):
            try:
                # Read image
                with open(image_path, 'rb') as image_file:
                    content = image_file.read()
                
                # Create image object
                image = vision.Image(content=content)
                
                # Perform OCR
                response = self.client.text_detection(image=image)
                
                if response.error.message:
                    raise Exception(
                        '{}\nFor more info on error messages, check: '
                        'https://cloud.google.com/apis/design/errors'.format(
                            response.error.message))
                
                # Extract text
                texts = response.text_annotations
                if texts:
                    full_text = texts[0].description
                    
                    # Extract fields for this page
                    page_fields = self.extract_invoice_fields(full_text, signature_flag, sticker_flag)
                    all_fields.append(page_fields)
                    
                    # Create page result
                    page_result = PageResult(
                        page=i + 1,
                        page_fields=page_fields,
                        updates_applied={}  # You can add update tracking here
                    )
                    page_results.append(page_result)
                    
                else:
                    # No text found
                    empty_fields = InvoiceFields(
                        invoice_number=None,
                        store_number=None,
                        invoice_date=None,
                        sticker_date=None,
                        total_quantity=None,
                        has_frito_lay=False,
                        has_signature=signature_flag,
                        has_sticker=sticker_flag,
                        is_valid="Invalid"
                    )
                    all_fields.append(empty_fields)
                    
                    page_result = PageResult(
                        page=i + 1,
                        page_fields=empty_fields,
                        updates_applied={}
                    )
                    page_results.append(page_result)
                    
            except Exception as e:
                print(f"Error processing image {image_path}: {e}")
                # Create error page result
                error_fields = InvoiceFields(
                    invoice_number=None,
                    store_number=None,
                    invoice_date=None,
                    sticker_date=None,
                    total_quantity=None,
                    has_frito_lay=False,
                    has_signature=signature_flag,
                    has_sticker=sticker_flag,
                    is_valid="Invalid"
                )
                all_fields.append(error_fields)
                
                page_result = PageResult(
                    page=i + 1,
                    page_fields=error_fields,
                    updates_applied={}
                )
                page_results.append(page_result)
        
        # Combine fields from all pages
        master_fields = self._combine_fields(all_fields)
        
        # Set sticker_date to "Not Available" if no sticker detected
        if not sticker_flag:
            master_fields.sticker_date = "Not Available"
        
        # Create final result
        result = OCRResult(
            filename=filename,
            total_pages=len(image_paths),
            master_fields=master_fields,
            fields_found=self._get_found_fields(master_fields),
            page_details=page_results,
            processing_status="Success",
            error_message="",
            sticker_flag=sticker_flag,
            signature_flag=signature_flag
        )
        
        print(f"OCRResult created successfully: {result.filename}, status: {result.processing_status}")
        print(f"Master fields: {result.master_fields}")
        
        return result

    def _combine_fields(self, all_fields: list) -> InvoiceFields:
        """Combine fields from multiple pages, prioritizing non-None values"""
        if not all_fields:
            return InvoiceFields()
        
        # Start with the first set of fields
        combined = all_fields[0]
        
        # Update with non-None values from other pages
        for fields in all_fields[1:]:
            if fields.invoice_number and not combined.invoice_number:
                combined.invoice_number = fields.invoice_number
            if fields.store_number and not combined.store_number:
                combined.store_number = fields.store_number
            if fields.invoice_date and not combined.invoice_date:
                combined.invoice_date = fields.invoice_date
            if fields.sticker_date and not combined.sticker_date:
                combined.sticker_date = fields.sticker_date
            if fields.total_quantity is not None and combined.total_quantity is None:
                combined.total_quantity = fields.total_quantity
            if fields.has_frito_lay and not combined.has_frito_lay:
                combined.has_frito_lay = fields.has_frito_lay
            if fields.has_signature and not combined.has_signature:
                combined.has_signature = fields.has_signature
            if fields.has_sticker and not combined.has_sticker:
                combined.has_sticker = fields.has_sticker
        
        return combined

    def _get_found_fields(self, fields: InvoiceFields) -> list:
        """Get list of fields that were successfully extracted"""
        found = []
        if fields.invoice_number:
            found.append('invoice_number')
        if fields.store_number:
            found.append('store_number')
        if fields.invoice_date:
            found.append('invoice_date')
        if fields.sticker_date and fields.sticker_date != "Not Available":
            found.append('sticker_date')
        if fields.total_quantity is not None:
            found.append('total_quantity')
        if fields.has_frito_lay:
            found.append('has_frito_lay')
        if fields.has_signature:
            found.append('has_signature')
        if fields.has_sticker:
            found.append('has_sticker')
        if fields.is_valid:
            found.append('is_valid')
        return found

    def save_to_excel(self, result: OCRResult, filename: str, sticker_flag: bool):
        """Save OCR results to Excel file"""
        try:
            # Create output directory if it doesn't exist
            output_dir = Path(INFERENCE_OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Use consistent filename
            excel_path = output_dir / "target_results.xlsx"
            
            # Create Excel row
            excel_row = ExcelRow.from_ocr_result(result, sticker_flag)
            
            # Convert to dictionary
            row_dict = excel_row.model_dump()
            
            # Convert boolean values to strings to avoid Excel TRUE/FALSE
            for key, value in row_dict.items():
                if isinstance(value, bool):
                    if key == 'has_sticker':
                        row_dict[key] = "Yes" if value else "No"
                    elif key == 'has_signature':
                        row_dict[key] = "Yes" if value else "No"
                    elif key == 'has_frito_lay':
                        row_dict[key] = "Yes" if value else "No"
                    else:
                        row_dict[key] = "Yes" if value else "No"
            
            # Check if file exists
            if excel_path.exists():
                try:
                    # Read existing data
                    existing_df = pd.read_excel(excel_path)
                    
                    # Append new data
                    new_df = pd.DataFrame([row_dict])
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    
                    # Remove duplicates based on filename
                    combined_df = combined_df.drop_duplicates(subset=['filename'], keep='last')
                    
                    # Save combined data
                    combined_df.to_excel(excel_path, index=False)
                    print(f"Data for {filename} successfully saved to {excel_path}")
                    
                except Exception as e:
                    print(f"Error reading existing file, creating new one: {e}")
                    df = pd.DataFrame([row_dict])
                    df.to_excel(excel_path, index=False)
                    print(f"Created new file with data for {filename}")
            else:
                # Create new file
                df = pd.DataFrame([row_dict])
                df.to_excel(excel_path, index=False)
                print(f"Created new file with data for {filename}")
                
        except Exception as e:
            print(f"Error saving to Excel: {e}")
