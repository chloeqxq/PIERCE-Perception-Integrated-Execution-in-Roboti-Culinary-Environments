import cv2
import sys
'''

teleoperation:
lerobot-teleoperate --robot.type=bi_so_follower --teleop.type=bi_so_leader --robot.id=bot --teleop.id=leader \
--robot.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00 \
--robot.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00 \
--teleop.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00 \
--teleop.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00 \

visualization:
left: 
python3 view_camera.py /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.1:1.0-video-index0
right:
python3 view_camera.py /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.3:1.0-video-index0

hub: upper right port.
    camera left: usb-0000:c3:00.3-1.1   /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.1:1.0-video-index0
    camera right: usb-0000:c3:00.3-1.3  /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.3:1.0-video-index0

    arm left: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00
    arm right: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00

    leader left: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00
    leader right: /dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00


hub plug order:
    cl, cr, al, ar, ll, lr

top: /dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0

sudo rmmod uvcvideo
sudo modprobe uvcvideo quirks=128

python3 view_camera.py /dev/v4l/by-path/pci-0000:c3:00.4-usbv2-0:1.3:1.0-video-index0
python3 view_camera.py /dev/video0
python3 view_camera.py /dev/v4l/by-id/usb-Arducam_Technology_Co.__Ltd._Arducam_OV9782_USB_Camera_UC852-video-index0
'''
# Example path for a specific Logitech webcam
path = "/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0"
path = sys.argv[1]
print(f"trying to read from {path}")
cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
cap.set(cv2.CAP_PROP_FOURCC, fourcc)
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)
# Set frame rate to 30 FPS
cap.set(cv2.CAP_PROP_FPS, 30)
print("stream configured")

while True:
    # 2. Capture frame-by-frame. ret is a boolean (True if frame is read).
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame (stream end?). Exiting...")
        break

    # 3. Display the resulting frame
    cv2.imshow('Webcam Feed', frame)

    # 4. Stop the loop if the 'q' key is pressed
    if cv2.waitKey(1) == ord('q'):
        break

# 5. When everything is done, release the capture and close windows
cap.release()
cv2.destroyAllWindows()