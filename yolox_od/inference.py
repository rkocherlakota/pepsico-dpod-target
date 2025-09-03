#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
Robust YOLOX inference script that works with PyTorch 2.6+ (weights_only default)
- Handles checkpoints saved as {"model": state_dict} or {"state_dict": ...} or raw state_dict
- Avoids UnpicklingError by explicitly setting weights_only=False when supported
- Falls back to allowlisting numpy scalar for ultra-conservative environments
- Minimal, single-image inference + visualization

Usage:
  python inference.py \
    --exp exps/example/custom/yolox_s.py \
    --ckpt YOLOX_outputs/yolox_s/best_ckpt.pth \
    --img path/to/your.jpg \
    --conf 0.25 --nms 0.65 --device cuda
"""
import os
import sys
import argparse
import inspect
import warnings

import cv2
import numpy as np
import torch
from .config import EXP_FILE, CKPT_PATH, CONF_THRES, NMS_THRES, DEVICE

# Ensure YOLOX root is importable when running from repo root
sys.path.insert(0, os.path.abspath("."))

from yolox.exp import get_exp
from yolox.utils import fuse_model, postprocess, vis

try:
    from yolox.data.data_augment import preproc
except Exception as e:
    raise ImportError("Failed to import YOLOX preproc. Are you running inside the YOLOX repo root?") from e


def smart_torch_load(path: str):
    """Load a checkpoint robustly across PyTorch versions.

    PyTorch 2.6 made torch.load(weights_only=True) the default which can break
    older checkpoints. We try the safest thing first, then degrade gracefully.
    """
    # Path checks
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    sig = inspect.signature(torch.load)
    has_weights_only = "weights_only" in sig.parameters

    # 1) Prefer explicitly disabling weights_only if available (older YOLOX ckpts often need this)
    if has_weights_only:
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except Exception as e:
            warnings.warn(
                f"torch.load(weights_only=False) failed with: {e}\n"
                "Attempting safe_globals allowlist fallback..."
            )
            # 2) Fallback: allowlist numpy scalar for weights_only=True load
            try:
                torch.serialization.add_safe_globals([np.core.multiarray.scalar])
            except Exception:
                pass
            with torch.serialization.safe_globals([np.core.multiarray.scalar]):
                return torch.load(path, map_location="cpu", weights_only=True)
    else:
        # Older PyTorch without weights_only arg
        return torch.load(path, map_location="cpu")


def extract_state_dict(ckpt: dict):
    """Extract a state_dict from various checkpoint layouts."""
    if isinstance(ckpt, dict):
        if "model" in ckpt and isinstance(ckpt["model"], dict):
            return ckpt["model"]
        if "state_dict" in ckpt and isinstance(ckpt["state_dict"], dict):
            return ckpt["state_dict"]
        # Some exporters save the state dict at the root
        keys = list(ckpt.keys())
        if keys and all(k.startswith(("backbone.", "head.", "module.", "stem.")) or "." in k for k in keys):
            return ckpt
    raise ValueError("Unsupported checkpoint format: cannot find model/state_dict.")


def get_class_names(exp):
    # YOLOX experiments typically define either `class_names` or `names`
    for attr in ("class_names", "names"):
        if hasattr(exp, attr) and getattr(exp, attr) is not None:
            return getattr(exp, attr)
    # Fallback to COCO if none provided
    try:
        from yolox.data.datasets import COCO_CLASSES
        return COCO_CLASSES
    except Exception:
        return None


# def run_inference(exp_file, ckpt_path, image_path, conf_thres, nms_thres, device):
def run_inference(image):
    # Load experiment & model
    exp = get_exp(EXP_FILE, None)
    model = exp.get_model()
    model.eval()

    # Load checkpoint robustly
    ckpt = smart_torch_load(CKPT_PATH)
    state_dict = extract_state_dict(ckpt)
    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    if missing:
        warnings.warn(f"Missing keys when loading state_dict: {missing[:10]}{'...' if len(missing)>10 else ''}")
    if unexpected:
        warnings.warn(f"Unexpected keys when loading state_dict: {unexpected[:10]}{'...' if len(unexpected)>10 else ''}")

    # Fuse for speed & move to device
    device = torch.device(DEVICE if torch.cuda.is_available() and DEVICE.startswith("cuda") else "cpu")
    model = fuse_model(model).to(device)

    # Read image
    # img = cv2.imread(image)
    if image is None:
        raise FileNotFoundError(f"Image not found: {image}")

    # Preprocess -> preproc expects BGR, returns CHW float32, and resize ratio
    img_processed, ratio = preproc(image, exp.test_size)
    img_tensor = torch.from_numpy(img_processed).unsqueeze(0).float().to(device)

    # Inference
    with torch.no_grad():
        outputs = model(img_tensor)
        outputs = postprocess(
            outputs,
            num_classes=exp.num_classes,
            conf_thre=CONF_THRES,
            nms_thre=NMS_THRES,
        )

    # Visualize
    if outputs[0] is not None:
        pred = outputs[0].cpu()
        bboxes = pred[:, 0:4] / ratio  # de-scale to original image size
        scores = pred[:, 4] * pred[:, 5]
        cls_ids = pred[:, 6]

        class_names = get_class_names(exp)
        vis_img, op_results = vis(image, bboxes, scores, cls_ids, conf=CONF_THRES, class_names=class_names)
        
        # Create detection results with class names
        detection_results = []
        for i, cls_id in enumerate(cls_ids):
            if cls_id < len(class_names):
                detection_results.append(class_names[int(cls_id)])
        
        print(f"Raw detection results: {detection_results}")
        
        # saving img
        # save_path = os.path.splitext(os.path.basename(image))[0] + "_yolox.jpg"
        # cv2.imwrite(save_path, vis_img)
        # print(f"Saved: {save_path}")
    else:
        print("No objects detected above threshold.")
        detection_results = []
    
    return vis_img, detection_results


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--exp", default="exps/example/custom/yolox_s.py", help="Path to YOLOX exp file")
    p.add_argument("--ckpt", default="best_ckpt.pth", help="Path to checkpoint .pth")
    p.add_argument("--img", required=True, help="Path to input image")
    p.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    p.add_argument("--nms", type=float, default=0.65, help="NMS IoU threshold")
    p.add_argument("--device", default="cuda", help="cuda or cpu")
    return p.parse_args()


if __name__ == "__main__":
    # args = parse_args()
    op_img, op_results = run_inference(
        exp_file="exps/example/custom/yolox_s.py",
        ckpt_path='last_mosaic_epoch_ckpt_100eps.pth',  #"best_ckpt.pth",
        image_path="testing_samples/37338500_1.jpeg",
        conf_thres=0.25,
        nms_thres=0.65,
        device="cpu",
    )
    cv2.namedWindow("op_img", cv2.WINDOW_NORMAL)

    cv2.imshow("op_img", op_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
