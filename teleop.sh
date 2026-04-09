# !/bin/bash
lerobot-teleoperate --robot.type=bi_so_follower --teleop.type=bi_so_leader --robot.id=bot --teleop.id=leader \
--robot.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00 \
--robot.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00 \
--teleop.left_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00 \
--teleop.right_arm_config.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00 \