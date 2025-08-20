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

# Initialize client with credentials
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

class OCRProcessor:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient(credentials=credentials)

    def extract_invoice_fields(self, full_text: str) -> dict:
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        def first_match(patterns, text, flags=re.IGNORECASE):
            for p in patterns:
                m = re.search(p, text, flags)
                if m:
                    return m.group(1) if m.lastindex else m.group(0)
            return None

        invoice_patterns = [
            r"\bINVOICE\s*(?:NO\.?|#|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]+)\b",
            r"\bINV\s*(?:NO\.?|#)?\s*[:\-]?\s*([A-Z0-9\-]+)\b",
            r"\bDOCUMENT\s*(?:NO\.?|#|NUMBER)?\s*[:\-]?\s*([A-Z0-9\-]+)\b",
        ]
        invoice_number = first_match(invoice_patterns, full_text)

        store_patterns = [
            r"\bSTORE\s*#\s*[:\-]?\s*([A-Z0-9\-]{2,})\b",
            r"\bSTORE\s*NAME\b[^\n#]*#\s*([A-Z0-9\-]{2,})\b",
            r"\bSTORE\s*(?:NUMBER|NO\.?)\s*[:\-]?\s*([A-Z0-9\-]{2,})\b",
        ]
        store_number = first_match(store_patterns, full_text)

        invoice_date_pattern = r"\b(?:0?[1-9]|[12][0-9]|3[01])[\.\-/\s](?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\.\-/\s](?:20)?\d{2}\b"
        invoice_date_match = re.search(invoice_date_pattern, full_text, flags=re.IGNORECASE)
        invoice_date = invoice_date_match.group(0) if invoice_date_match else None

        sticker_date_pattern = r"\b(?:0?[1-9]|1[0-2])[\-/\.](?:0?[1-9]|[12][0-9]|3[01])[\-/\.]((?:20)?\d{2})\b"
        sticker_match = re.search(sticker_date_pattern, full_text)
        sticker_date = sticker_match.group(0) if sticker_match else None

        total_qty = None
        total_qty_patterns = [
            r"\bTOTAL\s*(?:QTY|QUANTITY)\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\b(?:QTY|QUANTITY)\s*TOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\b",
            r"\bTOTAL\s*[:\-]?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:QTY|QUANTITY)\b",
        ]
        for line in lines:
            if re.search(r"\b(QTY|QUANTITY|TOTAL)\b", line, re.IGNORECASE):
                candidate = first_match(total_qty_patterns, line)
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

        return {
            "invoice_number": invoice_number,
            "store_number": store_number,
            "invoice_date": invoice_date,
            "sticker_date": sticker_date,
            "total_quantity": total_qty,
            "has_frito_lay": has_frito_lay,
            "has_signature": has_signature,
        }

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

    def save_to_excel(self, results: dict, filename: str):
        """
        Saves the extracted OCR data to an Excel sheet.
        It reads the existing file, appends the new data, and writes the full
        DataFrame back to ensure correct column alignment.
        """
        excel_path = os.path.join(INFERENCE_OUTPUT_DIR, "ocr_results.xlsx")

        # Define the desired column order
        columns = [
            'filename',
            'invoice_number',
            'store_number',
            'invoice_date',
            'sticker_date',
            'total_quantity',
            'has_frito_lay',
            'has_signature',
            'has_sticker',
            'is_valid'
        ]

        # Prepare the new data as a single-row DataFrame
        new_row_data = {
            'filename': filename,
            'invoice_number': results['master_fields']['invoice_number'],
            'store_number': results['master_fields']['store_number'],
            'invoice_date': self._normalize_date_string_to_common_format(results['master_fields']['invoice_date']),
            'sticker_date': self._normalize_date_string_to_common_format(results['master_fields']['sticker_date']),
            'total_quantity': results['master_fields']['total_quantity'],
            'has_frito_lay': results['master_fields']['has_frito_lay'],
            'has_signature': results['master_fields']['has_signature'],
            'has_sticker': results['master_fields']['sticker_date'] is not None,
            'is_valid': (results['master_fields']['sticker_date'] is not None and results['master_fields']['has_signature'])
        }
        
        new_df = pd.DataFrame([new_row_data])

        try:
            if os.path.exists(excel_path):
                # Read the existing data
                existing_df = pd.read_excel(excel_path)
                # Ensure the existing DataFrame has the correct columns and order
                for col in columns:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                existing_df = existing_df[columns]

                # Append the new DataFrame
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                # If the file doesn't exist, start with the new data
                combined_df = new_df[columns]

            # Write the entire combined DataFrame back to the Excel file
            combined_df.to_excel(excel_path, index=False)
            
            print(f"Data for {filename} successfully saved to {excel_path}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

    def process_images(self, image_paths: list, filename: str):
        master_fields = {
            "invoice_number": None,
            "store_number": None,
            "invoice_date": None,
            "sticker_date": None,
            "total_quantity": None,
            "has_frito_lay": False,
            "has_signature": False
        }
        
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
                for field_name, field_value in page_fields.items():
                    if field_name == "has_frito_lay":
                        if field_value and not master_fields[field_name]:
                            master_fields[field_name] = field_value
                            fields_found.add(field_name)
                            page_updates[field_name] = "UPDATED"
                    elif field_name == "has_signature":
                        if field_value and not master_fields[field_name]:
                            master_fields[field_name] = field_value
                            fields_found.add(field_name)
                            page_updates[field_name] = "UPDATED"
                    elif field_value is not None and field_name not in fields_found:
                        master_fields[field_name] = field_value
                        fields_found.add(field_name)
                        page_updates[field_name] = "UPDATED"
                    else:
                        page_updates[field_name] = "SKIPPED"
                
                all_results.append({
                    "page": page_num + 1,
                    "page_fields": page_fields,
                    "updates_applied": page_updates
                })
            
            except Exception as e:
                print(f"Error processing image {image_path}: {e}")
                continue

        final_results = {
            "total_pages": len(image_paths),
            "master_fields": master_fields,
            "fields_found": list(fields_found),
            "page_details": all_results
        }
        
        self.save_to_excel(final_results, filename)

        return final_results