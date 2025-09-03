import os
import uuid
import time
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from ocr_preprocessor import OCRProcessor
from werkzeug.utils import secure_filename
<<<<<<< HEAD
from yolox_od.inference import run_inference
import cv2
import numpy as np
=======
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152

# PDF → image
from pdf2image import convert_from_path

app = Flask(__name__)

<<<<<<< HEAD

#od related files
# exp_file="yolox_od/exps/example/custom/yolox_s.py",
# ckpt_path="yolox_od/last_mosaic_epoch_ckpt_100eps.pth",
# image_path="test.jpeg",
# conf_thres=0.25,
# nms_thres=0.65,
# device="cpu",

=======
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
# Initialize OCR processor
ocr_processor = OCRProcessor()

# === CONFIG ===
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTS = {"pdf", "jpg", "jpeg", "png"}
ALLOWED_MIME = {
    "application/pdf",
    "application/octet-stream",  # some clients/tools use this
    "image/jpeg",
    "image/png",
}

PDF_DPI = int(os.environ.get("PDF_DPI", "200"))
PDF_MAX_PAGES = os.environ.get("PDF_MAX_PAGES")  # e.g. "10" to cap pages
PDF_MAX_PAGES = int(PDF_MAX_PAGES) if PDF_MAX_PAGES else None

# If Poppler executables aren't in PATH, set POPPLER_PATH to the bin folder:
#   Windows example: set POPPLER_PATH=C:\poppler\bin
#   Linux/macOS: usually not needed if installed via apt/brew
POPPLER_PATH = os.environ.get("POPPLER_PATH")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part in form-data (expected key 'file')."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(f.filename):
        return jsonify({"error": "Only PDF, JPG, JPEG, PNG allowed."}), 400

    if (f.mimetype or "").lower() not in ALLOWED_MIME:
        return jsonify({"error": f"Unexpected Content-Type: {f.mimetype}"}), 400

    # Create a unique folder per upload to avoid name clashes
    base_name = Path(secure_filename(f.filename)).stem
    token = uuid.uuid4().hex[:8]
    upload_base = UPLOAD_DIR / f"{base_name}-{token}"
    upload_base.mkdir(parents=True, exist_ok=True)

    # Save original file
    ext = f.filename.rsplit(".", 1)[1].lower()
    original_path = upload_base / f"original.{ext}"
    try:
        f.save(original_path)
    except Exception as e:
        return jsonify({"error": f"Failed to save file: {e}"}), 500

    # If image, just return the saved path
    if ext in {"jpg", "jpeg", "png"}:
        return jsonify({
            "message": "Upload ok (image).",
            "original": str(original_path),
            "type": "image",
        }), 200

    # If PDF, convert pages to PNG
    pages_dir = upload_base / "pages"
    pages_dir.mkdir(exist_ok=True)

    try:
        # Convert PDF → PIL images
        pages = convert_from_path(
            str(original_path),
            dpi=PDF_DPI,
            poppler_path=POPPLER_PATH  # None uses PATH; string points to poppler bin
        )

        if PDF_MAX_PAGES is not None:
            pages = pages[:PDF_MAX_PAGES]

        page_paths = []
        for i, page in enumerate(pages, start=1):
            out_path = pages_dir / f"page_{i:03d}.png"
            page.save(out_path, "PNG")
            page_paths.append(str(out_path))

        return jsonify({
            "message": "Upload ok (pdf converted).",
            "original": str(original_path),
            "type": "pdf",
            "pages": page_paths,
            "page_count": len(page_paths)
        }), 200

    except Exception as e:
        # Common cause: Poppler missing/not in PATH
        hint = (
            "Install Poppler and/or set POPPLER_PATH. "
            "Ubuntu: apt install poppler-utils; macOS: brew install poppler; "
            "Windows: download build and set POPPLER_PATH to its 'bin' folder."
        )
        return jsonify({
            "error": f"Error converting PDF to images: {e}",
            "hint": hint
        }), 500


@app.route("/upload-document", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file part in form-data (expected key 'file')."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(f.filename):
        return jsonify({"error": "Only PDF, JPG, JPEG, PNG allowed."}), 400

    # Create a unique folder per upload to avoid name clashes
    base_name = Path(secure_filename(f.filename)).stem
    token = uuid.uuid4().hex[:8]
    upload_base = UPLOAD_DIR / f"{base_name}-{token}"
    upload_base.mkdir(parents=True, exist_ok=True)

    # Save original file
    ext = f.filename.rsplit(".", 1)[1].lower()
    original_path = upload_base / f"original.{ext}"
    try:
        f.save(original_path)
    except Exception as e:
        return jsonify({"error": f"Failed to save file: {e}"}), 500

    image_paths = []
    
    # If image, use it directly
    if ext in {"jpg", "jpeg", "png"}:
        image_paths.append(str(original_path))
    else:
        # If PDF, convert pages to PNG
        pages_dir = upload_base / "pages"
        pages_dir.mkdir(exist_ok=True)

        try:
            # Convert PDF → PIL images
            pages = convert_from_path(
                str(original_path),
                dpi=PDF_DPI,
                poppler_path=POPPLER_PATH
            )

            if PDF_MAX_PAGES is not None:
                pages = pages[:PDF_MAX_PAGES]

<<<<<<< HEAD
            detections_by_img_id = {}
            sticker_flag = False
            signature_flag = False
            for i, page in enumerate(pages):
                # load using cv2
                cv_img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
                cv_img_copy = cv_img.copy()
                op_img, op_results = run_inference(cv_img_copy)
                detections_by_img_id[i] = op_results
                # print("op_results : ", op_results)
                
                for det in op_results.get("detections", []):
                    label = det.get("label_text")
                    print("label : ", label)
                    if label == "receipt_outline":
                        print("label in receipt_outline : ", label)
                        bbox = det.get("bbox_xyxy")
                        x1, y1, x2, y2 = bbox
                        #crop the image
                        cv_img = cv_img[y1:y2, x1:x2]
                    elif label == "sticker":
                        print("label in sticker : ", label)
                        sticker_flag = True
                    elif label == "signature":
                        print("label in signature : ", label)
                        signature_flag = True

                out_path = pages_dir / f"page_{i:03d}.png"
                out_path_bbox = pages_dir / f"page_{i:03d}_viz.png"
                cv2.imwrite(out_path, cv_img)
                cv2.imwrite(out_path_bbox, op_img)
                # page.save(out_path, "PNG")
=======
            for i, page in enumerate(pages, start=1):
                out_path = pages_dir / f"page_{i:03d}.png"
                page.save(out_path, "PNG")
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
                image_paths.append(str(out_path))

        except Exception as e:
            hint = (
                "Install Poppler and/or set POPPLER_PATH. "
                "Ubuntu: apt install poppler-utils; macOS: brew install poppler; "
                "Windows: download build and set POPPLER_PATH to its 'bin' folder."
            )
            return jsonify({
                "error": f"Error converting PDF to images: {e}",
                "hint": hint
            }), 500

<<<<<<< HEAD
    # print("detections_by_img_id : ", detections_by_img_id)
 

    # Process images with OCR
    try:
        print("sticker_flag : ", sticker_flag)
        print("signature_flag : ", signature_flag)
        final_results = ocr_processor.process_images(image_paths, f.filename, sticker_flag, signature_flag)
                                                   # (image_paths, f.filename, sticker_flag, signature_flag)
=======
    # Process images with OCR
    try:
        import time
        from datetime import datetime
        
        # Record start time
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_timestamp = time.time()
        
        final_results = ocr_processor.process_images(image_paths, f.filename)
        
        # Record end time
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        end_timestamp = time.time()
        processing_time = end_timestamp - start_timestamp
        
        # Save to Excel with timing information
        ocr_processor.save_to_excel(final_results, f.filename, "Single", start_time, end_time, processing_time)
        
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
        # Convert Pydantic model to dict for JSON serialization
        return jsonify(final_results.model_dump()), 200
    except Exception as e:
        return jsonify({"error": f"Error processing images with OCR: {e}"}), 500


@app.route("/batch-process-files", methods=["POST"])
def batch_process_files():
    """Process multiple PDF files uploaded via form"""
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400
    
    files = request.files.getlist("files")
    
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files selected"}), 400
    
    # Filter for PDF files
    pdf_files = [f for f in files if f.filename.lower().endswith('.pdf')]
    
    if not pdf_files:
        return jsonify({"error": "No PDF files found in selection"}), 400
    
    try:
        # Create output directory
        output_dir = Path("inference_output")
        output_dir.mkdir(exist_ok=True)
        
<<<<<<< HEAD
        # Create output Excel file - use a single file for all batch results
        output_excel = output_dir / "target_results.xlsx"
=======
        # Create output Excel file - use single file for all results
        output_excel = output_dir / "dpod_target_results.xlsx"
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
        
        # Process each PDF file individually
        all_results = []
        successful = 0
        failed = 0
        
        for f in pdf_files:
            try:
<<<<<<< HEAD
                        # Create a unique temporary directory for this file
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # Save the PDF file
                            pdf_path = os.path.join(temp_dir, secure_filename(f.filename))
                            f.save(pdf_path)
                            
                            # Process the PDF using OCR processor directly
                            from ocr_preprocessor import OCRProcessor
                            ocr_processor = OCRProcessor()
                            
                            # Convert PDF to images
                            from pdf2image import convert_from_path
                            pages = convert_from_path(
                                pdf_path,
                                dpi=200,
                                poppler_path=os.environ.get("POPPLER_PATH")
                            )
                            
                            # Save pages as images
                            image_paths = []
                            # for i, page in enumerate(pages, start=1):
                            #     img_path = os.path.join(temp_dir, f"page_{i:03d}.png")
                            #     page.save(img_path, "PNG")
                            #     image_paths.append(img_path)
                            
                            detections_by_img_id = {}
                            # Initialize flags for THIS specific PDF file
                            file_sticker_flag = False
                            file_signature_flag = False
                            
                            for i, page in enumerate(pages, start=1):
                                # load using cv2
                                cv_img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
                                cv_img_copy = cv_img.copy()
                                op_img, op_results = run_inference(cv_img_copy)
                                detections_by_img_id[i] = op_results
                                # print("op_results : ", op_results)
                                for det in op_results.get("detections", []):
                                    label = det.get("label_text")
                                    if label == "receipt_outline":
                                        print("label in receipt_outline : ", label)
                                        bbox = det.get("bbox_xyxy")
                                        x1, y1, x2, y2 = bbox
                                        #crop the image
                                        cv_img = cv_img[y1:y2, x1:x2]
                                    elif label == "sticker":
                                        print("label in sticker : ", label)
                                        file_sticker_flag = True
                                    elif label == "signature":
                                        print("label in signature : ", label)
                                        file_signature_flag = True
                                print("sticker_flag for this file: ", file_sticker_flag)
                                print("signature_flag for this file: ", file_signature_flag)
                                # out_path = pages_dir / f"page_{i:03d}.png"
                                img_path = os.path.join(temp_dir, f"page_{i:03d}.png")
                                img_path_box = os.path.join(temp_dir, f"page_{i:03d}_viz.png")
                                # out_path_bbox = pages_dir / f"page_{i:03d}_viz.png"
                                # print("img_path : ", img_path)
                                cv2.imwrite(img_path, cv_img)
                                cv2.imwrite(img_path_box, op_img)
                                # page.save(out_path, "PNG")
                                image_paths.append(str(img_path))
                            
                            # Process with OCR
                            # result = ocr_processor.process_images(image_paths, f.filename)
                            result = ocr_processor.process_images(image_paths, f.filename, file_sticker_flag, file_signature_flag)

                            # Store the sticker and signature flags with the result for later use
                            result.sticker_flag = file_sticker_flag
                            result.signature_flag = file_signature_flag

                            all_results.append(result)
                            successful += 1
=======
                # Record start time for this file
                import time
                from datetime import datetime
                start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                start_timestamp = time.time()
                
                # Create a unique temporary directory for this file
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Save the PDF file
                    pdf_path = os.path.join(temp_dir, secure_filename(f.filename))
                    f.save(pdf_path)
                    
                    # Process the PDF using OCR processor directly
                    from ocr_preprocessor import OCRProcessor
                    ocr_processor = OCRProcessor()
                    
                    # Convert PDF to images
                    from pdf2image import convert_from_path
                    pages = convert_from_path(
                        pdf_path,
                        dpi=200,
                        poppler_path=os.environ.get("POPPLER_PATH")
                    )
                    
                    # Save pages as images
                    image_paths = []
                    for i, page in enumerate(pages, start=1):
                        img_path = os.path.join(temp_dir, f"page_{i:03d}.png")
                        page.save(img_path, "PNG")
                        image_paths.append(img_path)
                    
                    # Process with OCR
                    result = ocr_processor.process_images(image_paths, f.filename)
                    
                    # Record end time for this file
                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    end_timestamp = time.time()
                    processing_time = end_timestamp - start_timestamp
                    
                    # Add timing information to result
                    result.start_time = start_time
                    result.end_time = end_time
                    result.processing_time = processing_time
                    
                    all_results.append(result)
                    successful += 1
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
                    
            except Exception as e:
                print(f"Error processing {f.filename}: {e}")
                failed += 1
                # Create a failed result
                from models import OCRResult, InvoiceFields
                failed_result = OCRResult(
                    filename=f.filename,
                    total_pages=0,
                    master_fields=InvoiceFields(),
                    fields_found=[],
                    page_details=[],
                    processing_status="Failed",
                    error_message=str(e)
                )
                all_results.append(failed_result)
        
        # Save results to Excel
        from models import ExcelRow
        excel_rows = []
        for result in all_results:
            try:
<<<<<<< HEAD
                print("result : ", result)
                # Use the sticker_flag stored with each individual result
                if hasattr(result, 'sticker_flag'):
                    result_sticker_flag = result.sticker_flag
                else:
                    # Fallback for failed results or results without stored flags
                    result_sticker_flag = False
                
                print("sticker_flag for this result: ", result_sticker_flag)
                excel_row = ExcelRow.from_ocr_result(result, result_sticker_flag)
                print(f"excel_row : {excel_row}")
=======
                # Get timing information from result
                start_time = getattr(result, 'start_time', None)
                end_time = getattr(result, 'end_time', None)
                processing_time = getattr(result, 'processing_time', None)
                
                excel_row = ExcelRow.from_ocr_result(result, "Multiple", start_time, end_time, processing_time)
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
                excel_rows.append(excel_row)
            except Exception as e:
                print(f"Error creating ExcelRow: {e}")
                # Create a failed row
                excel_row = ExcelRow.from_failed_processing(
                    result.filename if hasattr(result, 'filename') else 'Unknown',
<<<<<<< HEAD
                    str(e)
=======
                    str(e),
                    "Multiple"
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
                )
                excel_rows.append(excel_row)
        
        # Convert to DataFrame and save - append to existing file if it exists
        import pandas as pd
        row_dicts = []
        for row in excel_rows:
            row_dict = row.model_dump()
            # Convert boolean values to strings to avoid Excel TRUE/FALSE
            for key, value in row_dict.items():
                if isinstance(value, bool):
<<<<<<< HEAD
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
        print(f"row_dicts : {row_dicts}")
        
        # Check if output file already exists and append to it
        if output_excel.exists():
            try:
                # Read existing data
                existing_df = pd.read_excel(output_excel)
                print(f"Existing file found with {len(existing_df)} rows")
                
                # Append new data
                new_df = pd.DataFrame(row_dicts)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                
                # Remove duplicates based on filename to avoid processing the same file multiple times
                combined_df = combined_df.drop_duplicates(subset=['filename'], keep='last')
                
                # Save combined data
                combined_df.to_excel(output_excel, index=False)
                print(f"Appended {len(new_df)} new rows to existing file. Total rows: {len(combined_df)}")
            except Exception as e:
                print(f"Error reading existing file, creating new one: {e}")
                df = pd.DataFrame(row_dicts)
                df.to_excel(output_excel, index=False)
        else:
            # Create new file
            df = pd.DataFrame(row_dicts)
            df.to_excel(output_excel, index=False)
            print(f"Created new file with {len(df)} rows")
        
        # Convert results to a format suitable for UI display
        results_for_ui = []
        for result in all_results:
            try:
                if hasattr(result, 'master_fields'):
                    # Successful result
                    results_for_ui.append({
                        'filename': result.filename,
                        'invoice_number': result.master_fields.invoice_number,
                        'store_number': result.master_fields.store_number,
                        'invoice_date': result.master_fields.invoice_date,
                        'sticker_date': result.master_fields.sticker_date,
                        'total_quantity': result.master_fields.total_quantity,
                        'has_frito_lay': 'Yes' if result.master_fields.has_frito_lay else 'No',
                        'has_signature': 'Yes' if result.master_fields.has_signature else 'No',
                        'has_sticker': 'Yes' if result.master_fields.has_sticker else 'No',
                        'processing_status': result.processing_status,
                        'is_valid': result.master_fields.is_valid
                    })
                else:
                    # Failed result
                    results_for_ui.append({
                        'filename': result.filename if hasattr(result, 'filename') else 'Unknown',
                        'invoice_number': None,
                        'store_number': None,
                        'invoice_date': None,
                        'sticker_date': None,
                        'total_quantity': None,
                        'has_frito_lay': 'No',
                        'has_signature': 'No',
                        'has_sticker': 'No',
                        'processing_status': 'Failed',
                        'is_valid': 'Invalid'
                    })
            except Exception as e:
                print(f"Error formatting result for UI: {e}")
                # Add a failed result entry
                results_for_ui.append({
                    'filename': 'Unknown',
                    'invoice_number': None,
                    'store_number': None,
                    'invoice_date': None,
                    'sticker_date': None,
                    'total_quantity': None,
                    'has_frito_lay': 'No',
                    'has_signature': 'No',
                    'has_sticker': 'No',
                    'processing_status': 'Failed',
                    'is_valid': 'Invalid'
                })

        return jsonify({
            "message": f"Batch processing completed. Success: {successful}, Failed: {failed}",
            "pdf_count": len(pdf_files),
            "output_file": str(output_excel),
            "results": results_for_ui,
            "successful": successful,
            "failed": failed
=======
                    row_dict[key] = "Yes" if value else "No"
            row_dicts.append(row_dict)
        
        new_df = pd.DataFrame(row_dicts)
        
        try:
            if output_excel.exists():
                # Read the existing data
                existing_df = pd.read_excel(output_excel)
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
            combined_df.to_excel(output_excel, index=False)
            
        except Exception as e:
            print(f"Error appending to Excel: {e}")
            # Fallback: save as new file
            new_df.to_excel(output_excel, index=False)
        
        return jsonify({
            "message": f"Batch processing completed. Success: {successful}, Failed: {failed}",
            "pdf_count": len(pdf_files),
            "output_file": str(output_excel)
>>>>>>> b4a4b82c9d6889d401a8a9f102c262e753bed152
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error during batch processing: {e}"}), 500


@app.route("/batch-process", methods=["POST"])
def batch_process():
    """Process multiple PDFs from a folder"""
    if "folder_path" not in request.form:
        return jsonify({"error": "No folder_path provided in form data"}), 400
    
    folder_path = request.form["folder_path"]
    
    if not os.path.exists(folder_path):
        return jsonify({"error": f"Folder does not exist: {folder_path}"}), 400
    
    if not os.path.isdir(folder_path):
        return jsonify({"error": f"Path is not a directory: {folder_path}"}), 400
    
    try:
        from batch_processor import BatchProcessor
        
        # Create batch processor
        processor = BatchProcessor(folder_path)
        
        # Get PDF files
        pdf_files = processor.get_pdf_files()
        
        if not pdf_files:
            return jsonify({"error": f"No PDF files found in: {folder_path}"}), 400
        
        # Process batch
        processor.process_batch()
        
        return jsonify({
            "message": "Batch processing completed successfully",
            "pdf_count": len(pdf_files),
            "output_file": str(processor.output_excel)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error during batch processing: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
