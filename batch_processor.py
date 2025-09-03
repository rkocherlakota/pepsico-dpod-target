import os
import time
from pathlib import Path
from pdf2image import convert_from_path
from ocr_preprocessor import OCRProcessor
from models import ExcelRow
import pandas as pd


class BatchProcessor:
    def __init__(self, input_folder, output_excel=None):
        self.input_folder = Path(input_folder)
        self.ocr_processor = OCRProcessor()
        
        # Use default output path if not specified
        if output_excel is None:
            from config import INFERENCE_OUTPUT_DIR
            self.output_excel = Path(INFERENCE_OUTPUT_DIR) / "target_results.xlsx"
        else:
            self.output_excel = Path(output_excel)
        
        # Ensure output directory exists
        self.output_excel.parent.mkdir(parents=True, exist_ok=True)
        
        # PDF processing settings
        self.pdf_dpi = 200
        self.pdf_max_pages = None
        self.poppler_path = None
        
    def get_pdf_files(self):
        """Get all PDF files from the input folder"""
        pdf_pattern = self.input_folder / "*.pdf"
        pdf_files = list(pdf_pattern.glob("*"))
        return sorted(pdf_files)
    
    def convert_pdf_to_images(self, pdf_path):
        """Convert PDF to images"""
        try:
            pages = convert_from_path(
                str(pdf_path),
                dpi=self.pdf_dpi,
                poppler_path=self.poppler_path
            )
            
            if self.pdf_max_pages is not None:
                pages = pages[:self.pdf_max_pages]
                
            # Save pages to temporary directory
            temp_dir = Path("temp_pages") / pdf_path.stem
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            image_paths = []
            for i, page in enumerate(pages, start=1):
                out_path = temp_dir / f"page_{i:03d}.png"
                page.save(out_path, "PNG")
                image_paths.append(str(out_path))
                
            return image_paths
            
        except Exception as e:
            print(f"Error converting PDF {pdf_path}: {e}")
            return []
    
    def process_single_pdf(self, pdf_path):
        """Process a single PDF file"""
        print(f"Processing: {pdf_path.name}")
        
        # Convert PDF to images
        image_paths = self.convert_pdf_to_images(pdf_path)
        
        if not image_paths:
            print(f"Failed to convert PDF: {pdf_path.name}")
            return None
        
        try:
            # Process with OCR - we need to get sticker and signature flags from somewhere
            # For now, we'll use default values
            sticker_flag = False  # This should come from OD model
            signature_flag = False  # This should come from OD model
            
            results = self.ocr_processor.process_images(image_paths, pdf_path.name, sticker_flag, signature_flag)
            
            # Clean up temporary images
            for img_path in image_paths:
                try:
                    os.remove(img_path)
                except:
                    pass
            
            # Try to remove temp directory
            try:
                temp_dir = Path("temp_pages") / pdf_path.stem
                if temp_dir.exists():
                    temp_dir.rmdir()
            except:
                pass
                
            return results
            
        except Exception as e:
            print(f"Error processing PDF {pdf_path.name}: {e}")
            return None
    
    def save_batch_results_to_excel(self, all_results):
        """Save all batch results to Excel"""
        if not all_results:
            print("No results to save")
            return
        
        # Convert results to ExcelRow objects
        excel_rows = []
        for result in all_results:
            if result is None:
                continue
            
            try:
                if hasattr(result, 'master_fields'):  # OCRResult object
                    excel_row = ExcelRow.from_ocr_result(result, result.sticker_flag if hasattr(result, 'sticker_flag') else False)
                else:  # Failed result dict
                    excel_row = ExcelRow.from_failed_processing(
                        result.get('filename', 'Unknown'),
                        result.get('error_message', 'Unknown error'))
                excel_rows.append(excel_row)
            except Exception as e:
                print(f"Error creating ExcelRow for result: {e}")
                # Create a failed row
                excel_row = ExcelRow.from_failed_processing(
                    result.get('filename', 'Unknown') if isinstance(result, dict) else 'Unknown',
                    str(e)
                )
                excel_rows.append(excel_row)
        
        try:
            # Convert rows to dicts - ensure boolean values are strings
            row_dicts = []
            for row in excel_rows:
                row_dict = row.model_dump()
                
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
                
                row_dicts.append(row_dict)
            
            # Check if output file already exists and append to it
            if self.output_excel.exists():
                try:
                    # Read existing data
                    existing_df = pd.read_excel(self.output_excel)
                    print(f"Existing file found with {len(existing_df)} rows")
                    
                    # Append new data
                    new_df = pd.DataFrame(row_dicts)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    
                    # Remove duplicates based on filename to avoid processing the same file multiple times
                    combined_df = combined_df.drop_duplicates(subset=['filename'], keep='last')
                    
                    # Save combined data
                    combined_df.to_excel(self.output_excel, index=False)
                    print(f"Appended {len(new_df)} new rows to existing file. Total rows: {len(combined_df)}")
                except Exception as e:
                    print(f"Error reading existing file, creating new one: {e}")
                    df = pd.DataFrame(row_dicts)
                    df.to_excel(self.output_excel, index=False)
            else:
                # Create new file
                df = pd.DataFrame(row_dicts)
                df.to_excel(self.output_excel, index=False)
                print(f"Created new file with {len(df)} rows")
            
            print(f"Batch results saved to: {self.output_excel}")
            print(f"Processed {len(excel_rows)} files successfully")
            
        except Exception as e:
            print(f"Error saving batch results to Excel: {e}")
            # Try to save raw data as fallback
            try:
                raw_data = []
                for row in excel_rows:
                    row_dict = row.model_dump()
                    raw_data.append(row_dict)
                
                # Use the same append logic for fallback
                if self.output_excel.exists():
                    try:
                        existing_df = pd.read_excel(self.output_excel)
                        new_df = pd.DataFrame(raw_data)
                        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                        combined_df = combined_df.drop_duplicates(subset=['filename'], keep='last')
                        combined_df.to_excel(self.output_excel, index=False)
                        print(f"Saved raw data to existing file {self.output_excel}")
                    except Exception as e2:
                        df = pd.DataFrame(raw_data)
                        df.to_excel(self.output_excel, index=False)
                        print(f"Saved raw data to new file {self.output_excel}")
                else:
                    df = pd.DataFrame(raw_data)
                    df.to_excel(self.output_excel, index=False)
                    print(f"Saved raw data to new file {self.output_excel}")
            except Exception as e2:
                print(f"Failed to save even raw data: {e2}")
    
    def process_batch(self):
        """Process all PDFs in the input folder"""
        pdf_files = self.get_pdf_files()
        
        if not pdf_files:
            print(f"No PDF files found in: {self.input_folder}")
            return
        
        print(f"Found {len(pdf_files)} PDF files to process")
        print(f"Input folder: {self.input_folder}")
        print(f"Output Excel: {self.output_excel}")
        print("-" * 50)
        
        start_time = time.time()
        all_results = []
        successful = 0
        failed = 0
        
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
            
            try:
                result = self.process_single_pdf(pdf_path)
                if result:
                    # Add filename to result if it's an OCRResult object
                    if hasattr(result, 'filename') and not result.filename:
                        result.filename = pdf_path.name
                    all_results.append(result)
                    successful += 1
                    print(f"✓ Successfully processed: {pdf_path.name}")
                else:
                    # Create a failed result entry
                    failed_result = {
                        'filename': pdf_path.name,
                        'error_message': 'Processing failed - no result returned'
                    }
                    all_results.append(failed_result)
                    failed += 1
                    print(f"✗ Failed to process: {pdf_path.name}")
                    
            except Exception as e:
                print(f"✗ Error processing {pdf_path.name}: {e}")
                # Create a failed result entry
                failed_result = {
                    'filename': pdf_path.name,
                    'error_message': str(e)
                }
                all_results.append(failed_result)
                failed += 1
        
        # Save results to Excel
        self.save_batch_results_to_excel(all_results)
        
        # Print summary
        end_time = time.time()
        processing_time = end_time - start_time
        
        print("-" * 50)
        print(f"Batch processing completed!")
        print(f"Total files: {len(pdf_files)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Results saved to: {self.output_excel}")
        
        return {
            'total_files': len(pdf_files),
            'successful': successful,
            'failed': failed,
            'processing_time': processing_time,
            'output_file': str(self.output_excel)
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python batch_processor.py <input_folder> [output_excel]")
        sys.exit(1)
    
    input_folder = sys.argv[1]
    output_excel = sys.argv[2] if len(sys.argv) > 2 else None
    
    processor = BatchProcessor(input_folder, output_excel)
    results = processor.process_batch()
    
    if results:
        print(f"\nBatch processing completed successfully!")
        print(f"Results: {results}")
    else:
        print("\nBatch processing failed!")
        sys.exit(1)
