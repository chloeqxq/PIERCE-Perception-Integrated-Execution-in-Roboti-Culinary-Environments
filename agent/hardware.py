import sys
import os
from pathlib import Path
from lerobot.robots import bi_so_follower,so_follower
from lerobot.teleoperators import bi_so_leader,so_leader
def get_platform_ports():
    """Returns ports configuration depending on the current OS."""
    # Check if we are running in WSL by looking for Microsoft kernel
    is_wsl = 'linux' in sys.platform and 'microsoft' in os.uname().release.lower()
    
    if is_wsl:
        # WSL mapping for COM6, COM7, COM8, COM9
        return {
            "follower_left": "/dev/ttyACM0",
            "follower_right": "/dev/ttyACM1",
            "leader_left": "/dev/ttyACM2",
            "leader_right": "/dev/ttyACM3",
        }
    else:
        # Default Linux /by-id/ mappings
        return {
            "follower_left": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00",
            "follower_right": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00",
            "leader_left": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00",
            "leader_right": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00",
        }


def get_platform_cameras():
    """Returns camera configuration depending on the current OS."""
    is_wsl = 'linux' in sys.platform and 'microsoft' in os.uname().release.lower()
    
    if is_wsl:
        return {
            "left_camera": 0,
            "right_camera": 2,
            "top_camera": 4,
        }
    else:
        # Default Linux /by-path/ and /by-id/ mappings
        host_port = 4
        return {
            # "left_camera": f"/dev/v4l/by-path/pci-0000:c3:00.{host_port}-usb-0:1.1:1.0-video-index0",
            # "right_camera": f"/dev/v4l/by-path/pci-0000:c3:00.{host_port}-usb-0:1.3:1.0-video-index0",
            "top_camera": "/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0",

            "left_camera": f"/dev/v4l/by-path/pci-0000:10:00.4-usb-0:1.1:1.0-video-index0",
            "right_camera": f"/dev/v4l/by-path/pci-0000:10:00.4-usb-0:1.3:1.0-video-index0",
        }
from lerobot.cameras.configs import Cv2Backends, Cv2Rotation

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig  # noqa: F401

def get_robot():
    cameras = get_platform_cameras()

    left_camera = OpenCVCameraConfig(
        index_or_path=cameras["left_camera"],
        width=640, height=480, fps=30, rotation=Cv2Rotation.ROTATE_180,backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    right_camera = OpenCVCameraConfig(
        index_or_path=cameras["right_camera"],
        width=640, height=480, fps=30, backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    top_camera = OpenCVCameraConfig(
        index_or_path=cameras["top_camera"],
        width=640, height=480, fps=30, backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    ports = get_platform_ports()

    robot = bi_so_follower.BiSOFollowerConfig(
            left_arm_config= so_follower.SO101FollowerConfig(
                port = ports["follower_left"],
                cameras= {"wrist":left_camera}

            ),
            right_arm_config= so_follower.SO101FollowerConfig(
                port = ports["follower_right"],
                cameras= {"wrist":right_camera,"top":top_camera}
            ),
            id = "bot",
            calibration_dir=Path('calibration/robots/so_follower')
        )
    return robot

def get_teleop():
    ports = get_platform_ports()
    teleop = bi_so_leader.BiSOLeaderConfig(
        left_arm_config=so_leader.SO101LeaderConfig(
            port = ports["leader_left"],
            invert_shoulder=False
        ),
        right_arm_config=so_leader.SO101LeaderConfig(
            port = ports["leader_right"],
            invert_shoulder=False
        ),
        id = "leader",
        calibration_dir=Path('calibration/teleoperators/so_leader')
    ),
    return teleop