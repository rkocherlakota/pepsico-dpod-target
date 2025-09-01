import os
import uuid
import time
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from ocr_preprocessor import OCRProcessor
from werkzeug.utils import secure_filename
from yolox_od.inference import run_inference
import cv2
import numpy as np

# PDF → image
from pdf2image import convert_from_path

app = Flask(__name__)


#od related files
# exp_file="yolox_od/exps/example/custom/yolox_s.py",
# ckpt_path="yolox_od/last_mosaic_epoch_ckpt_100eps.pth",
# image_path="test.jpeg",
# conf_thres=0.25,
# nms_thres=0.65,
# device="cpu",

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

            detections_by_img_id = {}
            for i, page in enumerate(pages):
                # load using cv2
                cv_img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
                cv_img_copy = cv_img.copy()
                op_img, op_results = run_inference(cv_img_copy)
                detections_by_img_id[i] = op_results
                # print("op_results : ", op_results)
                sticker_flag = False
                signature_flag = False
                for det in op_results.get("detections", []):
                    label = det.get("label_text")
                    if label == "receipt_outline":
                        bbox = det.get("bbox_xyxy")
                        x1, y1, x2, y2 = bbox
                        #crop the image
                        cv_img = cv_img[y1:y2, x1:x2]
                    elif label == "sticker":
                        sticker_flag = True
                    elif label == "signature":
                        signature_flag = True

                out_path = pages_dir / f"page_{i:03d}.png"
                out_path_bbox = pages_dir / f"page_{i:03d}_viz.png"
                cv2.imwrite(out_path, cv_img)
                cv2.imwrite(out_path_bbox, op_img)
                # page.save(out_path, "PNG")
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

    # print("detections_by_img_id : ", detections_by_img_id)
 

    # Process images with OCR
    try:
        # print("signature_flag : ", signature_flag)
        final_results = ocr_processor.process_images(image_paths, f.filename, sticker_flag, signature_flag)
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
        
        # Create output Excel file
        timestamp = int(time.time())
        output_excel = output_dir / f"batch_results_{timestamp}.xlsx"
        
        # Process each PDF file individually
        all_results = []
        successful = 0
        failed = 0
        
        for f in pdf_files:
            try:
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
                    for i, page in enumerate(pages, start=1):
                        # load using cv2
                        cv_img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
                        cv_img_copy = cv_img.copy()
                        op_img, op_results = run_inference(cv_img_copy)
                        detections_by_img_id[i] = op_results
                        # print("op_results : ", op_results)
                        sticker_flag = False
                        signature_flag = False
                        for det in op_results.get("detections", []):
                            label = det.get("label_text")
                            if label == "receipt_outline":
                                bbox = det.get("bbox_xyxy")
                                x1, y1, x2, y2 = bbox
                                #crop the image
                                cv_img = cv_img[y1:y2, x1:x2]
                            elif label == "sticker":
                                sticker_flag = True
                            elif label == "signature":
                                signature_flag = True

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
                    result = ocr_processor.process_images(image_paths, f.filename, sticker_flag, signature_flag)

                    all_results.append(result)
                    successful += 1
                    
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
                excel_row = ExcelRow.from_ocr_result(result, sticker_flag)
                # print(f"excel_row : {excel_row}")
                excel_rows.append(excel_row)
            except Exception as e:
                print(f"Error creating ExcelRow: {e}")
                # Create a failed row
                excel_row = ExcelRow.from_failed_processing(
                    result.filename if hasattr(result, 'filename') else 'Unknown',
                    str(e)
                )
                excel_rows.append(excel_row)
        
        # Convert to DataFrame and save
        import pandas as pd
        row_dicts = []
        for row in excel_rows:
            row_dict = row.model_dump()
            # Convert boolean values to strings to avoid Excel TRUE/FALSE
            for key, value in row_dict.items():
                if isinstance(value, bool):
                    row_dict[key] = "Yes" if value else "No"
            row_dicts.append(row_dict)
        # print(f"row_dicts : {row_dicts}")
        df = pd.DataFrame(row_dicts)
        df.to_excel(output_excel, index=False)
        
        return jsonify({
            "message": f"Batch processing completed. Success: {successful}, Failed: {failed}",
            "pdf_count": len(pdf_files),
            "output_file": str(output_excel)
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
