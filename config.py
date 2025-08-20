# config.py

import os

# Path to your Google Cloud Vision service account file
SERVICE_ACCOUNT_PATH = "global-lexicon-271715-bbd471224971_PROD.json"

# Output directories
INFERENCE_OUTPUT_DIR = "inference_output"
ANNOTATED_IMAGES_DIR = "annotated_images"
TEMP_UPLOAD_DIR = "uploads"

# Ensure output directories exist
os.makedirs(INFERENCE_OUTPUT_DIR, exist_ok=True)
os.makedirs(ANNOTATED_IMAGES_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)