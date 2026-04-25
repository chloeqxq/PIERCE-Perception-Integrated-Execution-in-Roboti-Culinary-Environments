from __future__ import annotations

import base64

import cv2
import numpy as np
import torch


IMAGE_KEYS = [
    "right_top",
    "left_wrist",
    "right_wrist",
]


def process_obs_for_agent(obs: dict) -> dict:
    payload = {
        "motor_angles": {},
        "images_base64": {},
    }

    for key in obs.keys():
        if key in IMAGE_KEYS:
            image_data = obs.get(key)
            if image_data is None:
                continue

            if torch.is_tensor(image_data):
                img_np = image_data.cpu().numpy()
            else:
                img_np = np.array(image_data)

            if len(img_np.shape) == 3 and img_np.shape[0] in [1, 3]:
                img_np = np.transpose(img_np, (1, 2, 0))

            if img_np.dtype != np.uint8:
                if img_np.max() <= 1.0:
                    img_np = (img_np * 255).astype(np.uint8)
                else:
                    img_np = img_np.astype(np.uint8)

            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode(".jpg", img_bgr)
            payload_key = "head" if key == "right_top" else key
            payload["images_base64"][payload_key] = base64.b64encode(buffer).decode("utf-8")
            continue

        value = obs.get(key)
        if value is None:
            continue

        if torch.is_tensor(value):
            payload["motor_angles"][key] = value.cpu().numpy().tolist()
        else:
            payload["motor_angles"][key] = np.array(value).tolist()

    return payload


def build_observation_payload(
    obs: dict,
    current_task: str,
    *,
    is_stale: bool = False,
    staleness_seconds: float | None = None,
    message: str | None = None,
) -> dict:
    payload = process_obs_for_agent(obs)
    payload["current_task"] = current_task
    payload["metadata"] = {
        "is_stale": is_stale,
        "staleness_seconds": staleness_seconds,
        "message": message,
    }
    return payload