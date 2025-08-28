import os
import glob
from pathlib import Path
from pdf2image import convert_from_path
from ocr_preprocessor import OCRProcessor
import pandas as pd
from datetime import datetime
import argparse
from models import ExcelRow, BatchProcessingResult
import time

class BatchProcessor:
    def __init__(self, input_folder, output_excel=None):
        self.input_folder = Path(input_folder)
        self.ocr_processor = OCRProcessor()
        
        # Use default output path if not specified
        if output_excel is None:
            from config import INFERENCE_OUTPUT_DIR
            self.output_excel = Path(INFERENCE_OUTPUT_DIR) / "dpod_target_results.xlsx"
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
            # Process with OCR
            results = self.ocr_processor.process_images(image_paths, pdf_path.name)
            
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
                    excel_row = ExcelRow.from_ocr_result(result)
                else:  # Failed result dict
                    excel_row = ExcelRow.from_failed_processing(
                        result.get('filename', 'Unknown'),
                        result.get('error_message', 'Unknown error')
                    )
                excel_rows.append(excel_row)
            except Exception as e:
                print(f"Error creating ExcelRow for result: {e}")
                # Create a failed row
                excel_row = ExcelRow.from_failed_processing(
                    result.get('filename', 'Unknown') if isinstance(result, dict) else 'Unknown',
                    str(e)
                )
                excel_rows.append(excel_row)
        
        # Convert to DataFrame and save to Excel - append to existing file
        try:
            # Convert rows to dicts - ensure boolean values are strings
            row_dicts = []
            for row in excel_rows:
                row_dict = row.model_dump()
                
                # Convert boolean values to strings to avoid Excel TRUE/FALSE
                for key, value in row_dict.items():
                    if isinstance(value, bool):
                        row_dict[key] = "Yes" if value else "No"
                
                row_dicts.append(row_dict)
            
            new_df = pd.DataFrame(row_dicts)
            
            # Check if file exists and append to it
            if self.output_excel.exists():
                # Read the existing data
                existing_df = pd.read_excel(self.output_excel)
                # Ensure the existing DataFrame has the correct columns
                for col in new_df.columns:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                existing_df = existing_df[list(new_df.columns)]
                
                # Append the new DataFrame
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                # If the file doesn't exist, start with the new data
                combined_df = new_df
            
            # Write the entire combined DataFrame back to the Excel file
            combined_df.to_excel(self.output_excel, index=False)
            
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
                df = pd.DataFrame(raw_data)
                df.to_excel(self.output_excel, index=False)
                print(f"Saved raw data to {self.output_excel}")
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
                    if hasattr(result, 'filename'):
                        result.filename = pdf_path.name
                    all_results.append(result)
                    successful += 1
                    print(f"✓ Success: {pdf_path.name}")
                else:
                    failed += 1
                    print(f"✗ Failed: {pdf_path.name}")
                    
            except Exception as e:
                failed += 1
                print(f"✗ Error processing {pdf_path.name}: {e}")
                all_results.append({
                    'filename': pdf_path.name,
                    'master_fields': {},
                    'processing_status': 'Failed',
                    'error_message': str(e)
                })
        
        processing_time = time.time() - start_time
        
        # Save results to Excel
        self.save_batch_results_to_excel(all_results)
        
        # Create batch processing result summary
        try:
            batch_result = BatchProcessingResult(
                total_files=len(pdf_files),
                successful=successful,
                failed=failed,
                output_file=str(self.output_excel),
                processing_time=processing_time,
                results=[ExcelRow.from_ocr_result(r) if hasattr(r, 'master_fields') else 
                        ExcelRow.from_failed_processing(r.get('filename', 'Unknown'), r.get('error_message', 'Unknown error'))
                        for r in all_results if r is not None]
            )
            
            print("-" * 50)
            print(f"Batch processing completed!")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Total: {len(pdf_files)}")
            print(f"Success Rate: {batch_result.success_rate:.1f}%")
            print(f"Processing Time: {processing_time:.2f} seconds")
            print(f"Results saved to: {self.output_excel}")
            
        except Exception as e:
            print(f"Error creating batch processing summary: {e}")
            print("-" * 50)
            print(f"Batch processing completed!")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Total: {len(pdf_files)}")
            print(f"Results saved to: {self.output_excel}")


def main():
    parser = argparse.ArgumentParser(description='Batch process PDFs with OCR')
    parser.add_argument('input_folder', help='Folder containing PDF files to process')
    parser.add_argument('--output', '-o', help='Output Excel file path (optional)')
    parser.add_argument('--dpi', type=int, default=200, help='PDF DPI for conversion (default: 200)')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to process per PDF')
    
    args = parser.parse_args()
    
    # Validate input folder
    if not os.path.exists(args.input_folder):
        print(f"Error: Input folder does not exist: {args.input_folder}")
        return
    
    # Create batch processor
    processor = BatchProcessor(args.input_folder, args.output)
    processor.pdf_dpi = args.dpi
    processor.pdf_max_pages = args.max_pages
    
    # Process batch
    processor.process_batch()


if __name__ == "__main__":
    main()
