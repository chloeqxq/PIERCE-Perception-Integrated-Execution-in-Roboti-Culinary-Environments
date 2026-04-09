import cv2

# Example path for a specific Logitech webcam
path = "/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0"
cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
