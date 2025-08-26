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
from config import SERVICE_ACCOUNT_PATH, INFERENCE_OUTPUT_DIR
from models import InvoiceFields, PageResult, OCRResult, ExcelRow

# Initialize client with credentials
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

class OCRProcessor:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient(credentials=credentials)

    def extract_invoice_fields(self, full_text: str) -> InvoiceFields:
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
                break

        sticker_date_pattern = r"\b(?:0?[1-9]|1[0-2])[\-/\.](?:0?[1-9]|[12][0-9]|3[01])[\-/\.]((?:20)?\d{2})\b"
        sticker_match = re.search(sticker_date_pattern, full_text)
        sticker_date = sticker_match.group(0) if sticker_match else None

        # Improved quantity patterns
        total_qty = None
        total_qty_patterns = [
            r"\bTOTAL\s*(?:QTY|QUANTITY)\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\b(?:QTY|QUANTITY)\s*TOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\bTOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:QTY|QUANTITY)\b",
            r"\bTOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\b(?:QTY|QUANTITY)\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\bAMOUNT\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\bTOTAL\s*EACHES\s*SOLD\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",  # Handle "TOTAL EACHES SOLD: 80"
        ]
        
        # First try to find quantity in lines containing quantity keywords
        for line in lines:
            if re.search(r"\b(QTY|QUANTITY|TOTAL|AMOUNT)\b", line, re.IGNORECASE):
                candidate = first_match(total_qty_patterns, line)
                if candidate:
                    try:
                        total_qty = float(candidate.replace(',', ''))
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

        has_signature = False
        try:
            normalized_lines = [ln.strip() for ln in full_text.splitlines()]
            start_idx = next(
                (i for i, ln in enumerate(normalized_lines)
                 if "signifies proof of delivery for quantities only" in ln.lower()),
                None,
            )
            end_idx = None
            if start_idx is not None:
                end_idx = next(
                    (i for i, ln in enumerate(normalized_lines[start_idx + 1 :], start=start_idx + 1)
                     if "sticker/store stamp" in ln.lower()),
                    None,
                )
            if start_idx is not None and end_idx is not None and end_idx > start_idx + 1:
                between = [ln for ln in normalized_lines[start_idx + 1 : end_idx] if ln]
                if len(between) > 0:
                    has_signature = True
        except Exception:
            has_signature = False

        if total_qty is not None and abs(total_qty) < 1e-9:
            total_qty = None


        
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

    def save_to_excel(self, results: OCRResult, filename: str):
        """
        Saves the extracted OCR data to an Excel sheet.
        It reads the existing file, appends the new data, and writes the full
        DataFrame back to ensure correct column alignment.
        """
        excel_path = os.path.join(INFERENCE_OUTPUT_DIR, "ocr_results.xlsx")

        # Create ExcelRow from OCRResult
        try:
            excel_row = ExcelRow.from_ocr_result(results)
        except Exception as e:
            print(f"Error creating ExcelRow from OCRResult: {e}")
            # Create a failed row
            excel_row = ExcelRow.from_failed_processing(filename, str(e))

        # Convert to DataFrame - ensure boolean values are strings
        row_dict = excel_row.model_dump()
        
        # Convert boolean values to strings to avoid Excel TRUE/FALSE
        for key, value in row_dict.items():
            if isinstance(value, bool):
                row_dict[key] = "Yes" if value else "No"
        
        new_df = pd.DataFrame([row_dict])

        try:
            if os.path.exists(excel_path):
                # Read the existing data
                existing_df = pd.read_excel(excel_path)
                # Ensure the existing DataFrame has the correct columns
                for col in excel_row.__fields__.keys():
                    if col not in existing_df.columns:
                        existing_df[col] = None
                existing_df = existing_df[list(excel_row.__fields__.keys())]

                # Append the new DataFrame
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                # If the file doesn't exist, start with the new data
                combined_df = new_df

            # Write the entire combined DataFrame back to the Excel file
            combined_df.to_excel(excel_path, index=False)
            
            print(f"Data for {filename} successfully saved to {excel_path}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

    def process_images(self, image_paths: list, filename: str) -> OCRResult:
        master_fields = InvoiceFields()
        fields_found = set()
        all_results = []
        
        for page_num, image_path in enumerate(image_paths):
            try:
                with io.open(image_path, 'rb') as image_file:
                    content = image_file.read()
                image = vision.Image(content=content)
                response = self.client.document_text_detection(image=image)
                full_text = response.full_text_annotation.text if response.full_text_annotation else ""
                
                page_fields = self.extract_invoice_fields(full_text)
                
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
        
        self.save_to_excel(final_results, filename)

        return final_results