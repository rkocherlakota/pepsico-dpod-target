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
import openpyxl  # Ensure this is installed
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

    def extract_invoice_fields(self, full_text: str, signature_flag : bool, has_sticker: bool = False, is_valid: str = "Invalid") -> InvoiceFields:
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
        # total_qty_patterns = [
        #     r"\bTOTAL\s*(?:QTY|QUANTITY)\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
        #     r"\b(?:QTY|QUANTITY)\s*TOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
        #     r"\bTOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:QTY|QUANTITY)\b",
        #     r"\bTOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
        #     r"\b(?:QTY|QUANTITY)\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
        #     r"\bAMOUNT\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
        #     r"\bTOTAL\s*EACHES\s*SOLD\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",  # Handle "TOTAL EACHES SOLD: 80"
        # ]
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
                        total_qty = float(candidate.replace(',', ''))
                        # print("total_qty : ", total_qty)
                    except ValueError:
                        pass
                    if total_qty is not None:
                        break
        
        # If not found, search in the entire text
        if total_qty is None:
            for pattern in total_qty_patterns:
                candidate = first_match([pattern], full_text)
                if candidate:
                    try:
                        total_qty = float(candidate.replace(',', ''))
                    except ValueError:
                        pass
                    if total_qty is not None:
                        break

        text_upper = full_text.upper()
        has_frito_lay = any(k in text_upper for k in ["FRITO LAY", "FRITO-LAY", "FRITOLAY", "FRITO  LAY", "FRITO"])

        has_signature = signature_flag

        if total_qty is not None and abs(total_qty) < 1e-9:
            total_qty = None


        
        # Ensure all dates are in MM/DD/YYYY format
        if invoice_date:
            original_invoice_date = invoice_date
            invoice_date = self._convert_date_format(invoice_date)
            print(f"Date conversion: {original_invoice_date} -> {invoice_date}")
        if sticker_date:
            original_sticker_date = sticker_date
            sticker_date = self._convert_date_format(sticker_date)
            print(f"Date conversion: {original_sticker_date} -> {sticker_date}")
        
        # Create and validate InvoiceFields object
        try:
            return InvoiceFields(
                invoice_number=invoice_number,
                store_number=store_number,
                invoice_date=invoice_date,
                sticker_date=sticker_date,
                total_quantity=total_qty,
                has_frito_lay=has_frito_lay,
                has_signature=has_signature,
                has_sticker=has_sticker,
                is_valid=is_valid,
            )
        except Exception as e:
            print(f"Validation error in extract_invoice_fields: {e}")
            # Return a default object with validation errors logged
            return InvoiceFields(
                invoice_number=invoice_number,
                store_number=store_number,
                invoice_date=invoice_date,
                sticker_date=sticker_date,
                total_quantity=total_qty,
                has_frito_lay=has_frito_lay,
                has_signature=has_signature,
                has_sticker=has_sticker,
                is_valid=is_valid,
            )

    def _normalize_date_string_to_common_format(self, date_str: str) -> str | None:
        if not date_str:
            return None
        candidate_formats = [
            "%d.%b.%Y", "%d.%B.%Y", "%d %b %Y", "%d %B %Y",
            "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d",
        ]
        for fmt in candidate_formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue
        return None

    def _convert_date_format(self, date_str: str) -> str:
        """Convert various date formats to MM/DD/YYYY format"""
        if not date_str:
            return date_str
        
        # Handle DD.MMM.YYYY format (e.g., "04.Jul.2025" -> "07/04/2025")
        dd_mmm_yyyy_pattern = r"(\d{1,2})\.(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.(\d{4})"
        match = re.match(dd_mmm_yyyy_pattern, date_str, re.IGNORECASE)
        if match:
            day, month, year = match.groups()
            print(f"DD.MMM.YYYY pattern matched: day={day}, month={month}, year={year}")
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = month_map.get(month.lower(), '01')
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month_num = month_num.zfill(2)
            # Convert DD.MMM.YYYY to MM/DD/YYYY (swap day and month)
            result = f"{month_num}/{day}/{year}"
            print(f"DD.MMM.YYYY conversion result: {result}")
            return result
        
        # Handle DD/MM/YYYY format (convert to MM/DD/YYYY)
        # This pattern should only match when the first number is > 12 (indicating it's a day)
        dd_mm_yyyy_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        match = re.match(dd_mm_yyyy_pattern, date_str)
        if match:
            first_num, second_num, year = match.groups()
            first_num_int = int(first_num)
            second_num_int = int(second_num)
            
            # If first number > 12, it's likely a day (DD/MM/YYYY)
            # If first number <= 12, it's likely a month (MM/DD/YYYY)
            if first_num_int > 12:
                day, month = first_num, second_num
                print(f"DD/MM/YYYY pattern matched: day={day}, month={month}, year={year}")
                # Ensure two-digit format for day and month
                day = day.zfill(2)
                month = month.zfill(2)
                # Convert DD/MM/YYYY to MM/DD/YYYY (swap day and month)
                result = f"{month}/{day}/{year}"
                print(f"DD/MM/YYYY conversion result: {result}")
                return result
            else:
                # This is likely MM/DD/YYYY format, just ensure consistent formatting
                month, day = first_num, second_num
                print(f"MM/DD/YYYY pattern matched: month={month}, day={day}, year={year}")
                # Ensure two-digit format for day and month
                day = day.zfill(2)
                month = month.zfill(2)
                result = f"{month}/{day}/{year}"
                print(f"MM/DD/YYYY formatting result: {result}")
                return result
        
        # Handle MMM DD, YYYY format (e.g., "Jul 04, 2025" -> "07/04/2025")
        mmm_dd_yyyy_pattern = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})"
        match = re.match(mmm_dd_yyyy_pattern, date_str, re.IGNORECASE)
        if match:
            month, day, year = match.groups()
            month_map = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = month_map.get(month.lower(), '01')
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month_num = month_num.zfill(2)
            return f"{month_num}/{day}/{year}"
        
        # Handle YYYY-MM-DD format
        yyyy_mm_dd_pattern = r"(\d{4})-(\d{1,2})-(\d{1,2})"
        match = re.match(yyyy_mm_dd_pattern, date_str)
        if match:
            year, month, day = match.groups()
            # Ensure two-digit format for day and month
            day = day.zfill(2)
            month = month.zfill(2)
            return f"{month}/{day}/{year}"
        

        
        # If no conversion needed, return as-is
        return date_str

    def save_to_excel(self, results: OCRResult, filename: str, sticker_flag:bool):
        """
        Saves the extracted OCR data to an Excel sheet.
        It reads the existing file, appends the new data, and writes the full
        DataFrame back to ensure correct column alignment.
        """
        excel_path = os.path.join(INFERENCE_OUTPUT_DIR, "target_results.xlsx")

        # Create ExcelRow from OCRResult
        try:
            excel_row = ExcelRow.from_ocr_result(results, sticker_flag)
            # print("excel_row from save_to_excel : ", excel_row)
        except Exception as e:
            print(f"Error creating ExcelRow from OCRResult: {e}")
            # Create a failed row
            excel_row = ExcelRow.from_failed_processing(filename, str(e))

        # print("excel_row : ", excel_row)
        # Convert to DataFrame - ensure boolean values are strings
        row_dict = excel_row.model_dump()
        # print("row_dict from save_to_excel after model_dump: ", row_dict)
        # Convert boolean values to strings to avoid Excel TRUE/FALSE
        for key, value in row_dict.items():
            if isinstance(value, bool):
                if key == 'has_sticker':
                    # has_sticker should reflect the OD model result
                    row_dict[key] = "Yes" if value else "No"
                elif key == 'has_signature':
                    # has_signature should reflect the OCR result
                    row_dict[key] = "Yes" if value else "No"
                elif key == 'has_frito_lay':
                    # has_frito_lay should reflect the OCR result
                    row_dict[key] = "Yes" if value else "No"
                else:
                    # For other boolean fields, convert as usual
                    row_dict[key] = "Yes" if value else "No"
                # print(f"from save_to_excel => {key} : {row_dict[key]}")
        
        new_df = pd.DataFrame([row_dict])
        # print("new_df start ocr results : ", new_df)

        try:
            if os.path.exists(excel_path):                # Read the existing data
                existing_df = pd.read_excel(excel_path)
                # print("existing_df : ", existing_df)
                # Ensure the existing DataFrame has the correct columns
                for col in excel_row.__fields__.keys():
                    if col not in existing_df.columns:
                        existing_df[col] = None
                existing_df = existing_df[list(excel_row.__fields__.keys())]

                # Fix the total_quantity column type in existing data to preserve "NA" values
                if 'total_quantity' in existing_df.columns:
                    # Replace any NaN values with "NA" in existing data, but keep numeric values as numbers
                    existing_df['total_quantity'] = existing_df['total_quantity'].fillna("NA")

                # Append the new DataFrame
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                # print("new_df : ", new_df)
                # If the file doesn't exist, start with the new data
                combined_df = new_df

            # print("combined_df ocr results : ", combined_df)

            # Write the entire combined DataFrame back to the Excel file
            # Ensure total_quantity column preserves "NA" values without converting numeric values to strings
            if 'total_quantity' in combined_df.columns:
                # Replace any NaN values with "NA", but preserve the original data types
                combined_df['total_quantity'] = combined_df['total_quantity'].fillna("NA")
            
            # Use ExcelWriter to apply consistent right alignment to total_quantity column
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name='Sheet1')
                
                # Get the worksheet to apply formatting
                worksheet = writer.sheets['Sheet1']
                
                # Apply right alignment to total_quantity column if it exists
                if 'total_quantity' in combined_df.columns:
                    # Find the column index for total_quantity
                    col_idx = combined_df.columns.get_loc('total_quantity') + 1  # +1 because Excel columns are 1-indexed
                    # Apply right alignment to the entire column (including header)
                    for row in range(1, len(combined_df) + 2):  # +2 because Excel rows are 1-indexed and we have header
                        cell = worksheet.cell(row=row, column=col_idx)
                        cell.alignment = openpyxl.styles.Alignment(horizontal='right')
            
            print(f"Data for {filename} successfully saved to {excel_path}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

    def _read_fields_from_excel(self, filename: str) -> tuple[bool, str]:
        """Read has_sticker and is_valid values from target_results.xlsx file"""
        try:
            excel_path = Path(INFERENCE_OUTPUT_DIR) / "target_results.xlsx"
            if not excel_path.exists():
                print(f"Excel file {excel_path} not found, using default values")
                return False, "Invalid"
            
            # Read the Excel file
            df = pd.read_excel(excel_path)
            
            # Look for the row with matching filename
            if 'filename' in df.columns:
                matching_row = df[df['filename'] == filename]
                if not matching_row.empty:
                    has_sticker = False
                    is_valid = "Invalid"
                    
                    # Check if has_sticker column exists
                    if 'has_sticker' in df.columns:
                        has_sticker_value = matching_row.iloc[0]['has_sticker']
                        # Convert to boolean
                        if isinstance(has_sticker_value, bool):
                            has_sticker = has_sticker_value
                        elif isinstance(has_sticker_value, str):
                            has_sticker = has_sticker_value.upper() in ['TRUE', 'YES', '1', 'Y']
                        elif isinstance(has_sticker_value, (int, float)):
                            has_sticker = bool(has_sticker_value)
                    
                    # Check if is_valid column exists
                    if 'is_valid' in df.columns:
                        is_valid_value = matching_row.iloc[0]['is_valid']
                        if isinstance(is_valid_value, str):
                            is_valid = is_valid_value
                        else:
                            is_valid = "Invalid"
                    
                    return has_sticker, is_valid
                else:
                    print(f"Filename {filename} not found in Excel file")
                    return False, "Invalid"
            else:
                print(f"filename column not found in Excel file")
                return False, "Invalid"
                
        except Exception as e:
            print(f"Error reading fields from Excel: {e}")
            return False, "Invalid"

    def process_images(self, image_paths: list, filename: str, sticker_flag: bool, signature_flag:bool) -> OCRResult:
        master_fields = InvoiceFields()
        fields_found = set()
        all_results = []
        
        # Use sticker_flag from OD model detection instead of reading from Excel
        # This ensures we get real-time sticker detection from the model
        
        for page_num, image_path in enumerate(image_paths):
            try:
                with io.open(image_path, 'rb') as image_file:
                    content = image_file.read()
                image = vision.Image(content=content)
                response = self.client.document_text_detection(image=image)
                full_text = response.full_text_annotation.text if response.full_text_annotation else ""
                
                # Pass sticker_flag from OD model to extract_invoice_fields
                page_fields = self.extract_invoice_fields(full_text, signature_flag, sticker_flag, "Invalid")
                
                # Set has_sticker based on OD model detection
                page_fields.has_sticker = sticker_flag
                
                page_updates = {}
                # Handle all fields - update if new value is better (not None)
                for field_name, field_value in page_fields.model_dump().items():
                    current_value = getattr(master_fields, field_name)
                    
                    # Update if:
                    # 1. Current value is None and new value is not None, OR
                    # 2. Current value is None/empty and new value is not None/empty
                    should_update = False
                    
                    if current_value is None and field_value is not None:
                        should_update = True
                    elif isinstance(current_value, str) and not current_value.strip() and field_value is not None:
                        should_update = True
                    elif isinstance(current_value, (int, float)) and current_value == 0 and field_value is not None and field_value != 0:
                        should_update = True
                    
                    if should_update:
                        setattr(master_fields, field_name, field_value)
                        if field_name not in fields_found:
                            fields_found.add(field_name)
                        page_updates[field_name] = "UPDATED"
                    else:
                        page_updates[field_name] = "SKIPPED"
                
                page_result = PageResult(
                    page=page_num + 1,
                    page_fields=page_fields,
                    updates_applied=page_updates
                )
                all_results.append(page_result)
            
            except Exception as e:
                print(f"Error processing image {image_path}: {e}")
                continue
        
        # Set has_sticker and is_valid based on OD model detection
        master_fields.has_sticker = sticker_flag
        
        # If no sticker detected by OD model, set sticker_date to "Not Available"
        if not sticker_flag:
            master_fields.sticker_date = "Not Available"
        
        master_fields.is_valid = "Valid" if (sticker_flag and signature_flag) else "Invalid"
        if sticker_flag:
            fields_found.add('has_sticker')
        if master_fields.is_valid:
            fields_found.add('is_valid')
        
        # Create and validate OCRResult
        try:
            final_results = OCRResult(
                filename=filename,
                total_pages=len(image_paths),
                master_fields=master_fields,
                fields_found=list(fields_found),
                page_details=all_results,
                processing_status="Success"
            )
        except Exception as e:
            print(f"Error creating OCRResult: {e}")
            # Create a failed result
            final_results = OCRResult(
                filename=filename,
                total_pages=len(image_paths),
                master_fields=master_fields,
                fields_found=list(fields_found),
                page_details=all_results,
                processing_status="Failed",
                error_message=str(e)
            )
        
        self.save_to_excel(final_results, filename, sticker_flag)

        return final_results