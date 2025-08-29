# config.py

import os

# Path to your Google Cloud Vision service account file
EXP_FILE = "yolox_od/exps/example/custom/yolox_s.py"
CKPT_PATH = "last_mosaic_epoch_ckpt_100eps.pth"
# image_path="test.jpeg",
CONF_THRES = 0.25
NMS_THRES = 0.65
DEVICE = "cpu"