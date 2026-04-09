# !/bin/bash
lerobot-teleoperate --robot.type=bi_so_follower --teleop.type=bi_so_leader --robot.id=bot --teleop.id=leader \
--robot.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00 \
--robot.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00 \
--teleop.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00 \
--teleop.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00 \
# --robot.left_arm_config.cameras='{
#     wrist: {"type": "opencv", "index_or_path": /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.1:1.0-video-index0,
#     "width": 640, "height": 480, "fps": 30, "rotation":ROTATE_180,"backend":V4L2,"fourcc":MJPG},}' \
# --robot.right_arm_config.cameras='{
#     wrist: {"type": "opencv", "index_or_path": /dev/v4l/by-path/pci-0000:c3:00.3-usb-0:1.3:1.0-video-index0,
#     "width": 640, "height": 480, "fps": 30, "backend":V4L2, "fourcc":MJPG},}' \
--display_data=true