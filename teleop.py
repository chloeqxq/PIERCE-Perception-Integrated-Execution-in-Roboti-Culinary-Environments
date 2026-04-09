# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Simple script to control a robot from teleoperation.

Example:

```shell
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem58760431541 \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \
    --robot.id=black \
    --teleop.type=so101_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \
    --teleop.id=blue \
    --display_data=true
```

Example teleoperation with bimanual so100:

```shell
lerobot-teleoperate \
  --robot.type=bi_so_follower \
  --robot.left_arm_config.port=/dev/tty.usbmodem5A460822851 \
  --robot.right_arm_config.port=/dev/tty.usbmodem5A460814411 \
  --robot.id=bimanual_follower \
  --robot.left_arm_config.cameras='{
    wrist: {"type": "opencv", "index_or_path": 1, "width": 640, "height": 480, "fps": 30},
  }' --robot.right_arm_config.cameras='{
    wrist: {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30},
  }' \
  --teleop.type=bi_so_leader \
  --teleop.left_arm_config.port=/dev/tty.usbmodem5A460852721 \
  --teleop.right_arm_config.port=/dev/tty.usbmodem5A460819811 \
  --teleop.id=bimanual_leader \
  --display_data=true
```

"""

import logging
import time
from dataclasses import asdict, dataclass
from pprint import pformat

import rerun as rr

from lerobot.cameras.configs import Cv2Backends, Cv2Rotation
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig  # noqa: F401
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig  # noqa: F401
from lerobot.processor import (
    RobotAction,
    RobotObservation,
    RobotProcessorPipeline,
    make_default_processors,
)
from lerobot.robots import (  # noqa: F401
    Robot,
    RobotConfig,
    bi_openarm_follower,
    bi_so_follower,
    earthrover_mini_plus,
    hope_jr,
    koch_follower,
    make_robot_from_config,
    omx_follower,
    openarm_follower,
    reachy2,
    so_follower,
    unitree_g1 as unitree_g1_robot,
)
from lerobot.teleoperators import (  # noqa: F401
    Teleoperator,
    TeleoperatorConfig,
    bi_openarm_leader,
    bi_so_leader,
    gamepad,
    homunculus,
    keyboard,
    koch_leader,
    make_teleoperator_from_config,
    omx_leader,
    openarm_leader,
    # openarm_mini,
    reachy2_teleoperator,
    so_leader,
    unitree_g1,
)
from lerobot.utils.import_utils import register_third_party_plugins
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import init_logging, move_cursor_up
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data
import numpy as np
print("done importing")

@dataclass
class TeleoperateConfig:
    # TODO: pepijn, steven: if more robots require multiple teleoperators (like lekiwi) its good to make this possibele in teleop.py and record.py with List[Teleoperator]
    teleop: TeleoperatorConfig
    robot: RobotConfig
    # Limit the maximum frames per second.
    fps: int = 60
    teleop_time_s: float | None = None
    # Display all cameras on screen
    display_data: bool = False
    # Display data on a remote Rerun server
    display_ip: str | None = None
    # Port of the remote Rerun server
    display_port: int | None = None
    # Whether to  display compressed images in Rerun
    display_compressed_images: bool = False


def teleop_loop(
    teleop: Teleoperator,
    robot: Robot,
    fps: int,
    teleop_action_processor: RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction],
    robot_action_processor: RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction],
    robot_observation_processor: RobotProcessorPipeline[RobotObservation, RobotObservation],
    display_data: bool = False,
    duration: float | None = None,
    display_compressed_images: bool = False,
):
    """
    This function continuously reads actions from a teleoperation device, processes them through optional
    pipelines, sends them to a robot, and optionally displays the robot's state. The loop runs at a
    specified frequency until a set duration is reached or it is manually interrupted.

    Args:
        teleop: The teleoperator device instance providing control actions.
        robot: The robot instance being controlled.
        fps: The target frequency for the control loop in frames per second.
        display_data: If True, fetches robot observations and displays them in the console and Rerun.
        display_compressed_images: If True, compresses images before sending them to Rerun for display.
        duration: The maximum duration of the teleoperation loop in seconds. If None, the loop runs indefinitely.
        teleop_action_processor: An optional pipeline to process raw actions from the teleoperator.
        robot_action_processor: An optional pipeline to process actions before they are sent to the robot.
        robot_observation_processor: An optional pipeline to process raw observations from the robot.
    """

    display_len = max(len(key) for key in robot.action_features)
    start = time.perf_counter()
    print("zeroing leaders")
    obs = robot.get_observation()
    _ = teleop.send_feedback(obs)
    _ = input("zeroing leaders, type anything to continue")
    teleop.disable_torque()

    while True:
        loop_start = time.perf_counter()

        # Get robot observation
        # Not really needed for now other than for visualization
        # teleop_action_processor can take None as an observation
        # given that it is the identity processor as default
        obs = robot.get_observation()

        # Get teleop action
        raw_action = teleop.get_action()

        # Process teleop action through pipeline
        teleop_action = teleop_action_processor((raw_action, obs))
        # print(teleop_action)
        # Process action for robot through pipeline
        robot_action_to_send = robot_action_processor((teleop_action, obs))
        error_dict = {}
        for key in robot_action_to_send.keys():
            if key in obs.keys():
                error_dict[key] = robot_action_to_send[key]-obs[key]
        joint_errors = np.array(list(error_dict.values()))
        # import ipdb
        # ipdb.set_trace()
        left_loads = np.array(list(robot.left_arm.bus.sync_read("Present_Current").values()))
        right_loads = np.array(list(robot.right_arm.bus.sync_read("Present_Current").values()))

        max_left = np.max(np.abs(left_loads))
        max_right = np.max(np.abs(right_loads))
        print(f"max left load: {max_left} max right load: {max_right}")
        if(max_left>35 or max_right>35):
            try:
                _ = teleop.send_feedback(obs)
            except:
                print("warning, cannot feedback")
            # pass
        else:
            try:
                teleop.disable_torque()
            except:
                pass
        # import ipdb

        # ipdb.set_trace()
        # Send processed action to robot (robot_action_processor.to_output should return RobotAction)
        _ = robot.send_action(robot_action_to_send)

        if display_data:
            # Process robot observation through pipeline
            obs_transition = robot_observation_processor(obs)

            log_rerun_data(
                observation=obs_transition,
                action=teleop_action,
                compress_images=display_compressed_images,
            )

            print("\n" + "-" * (display_len + 10))
            print(f"{'NAME':<{display_len}} | {'NORM':>7}")
            # Display the final robot action that was sent
            for motor, value in robot_action_to_send.items():
                print(f"{motor:<{display_len}} | {value:>7.2f}")
            print("OBS:")
            for motor, value in obs.items():
                try:
                    print(f"{motor:<{display_len}} | {value:>7.2f}")
                except:
                    pass
            move_cursor_up(len(robot_action_to_send) + 3)
        dt_s = time.perf_counter() - loop_start
        precise_sleep(max(1 / fps - dt_s, 0.0))
        loop_s = time.perf_counter() - loop_start
        print(f"Teleop loop time: {loop_s * 1e3:.2f}ms ({1 / loop_s:.0f} Hz)")
        move_cursor_up(1)

        if duration is not None and time.perf_counter() - start >= duration:
            return


def teleoperate(cfg: TeleoperateConfig):
    print("done parsing")
    init_logging()
    logging.info(pformat(asdict(cfg)))
    if cfg.display_data:
        init_rerun(session_name="teleoperation", ip=cfg.display_ip, port=cfg.display_port)
    display_compressed_images = (
        True
        if (cfg.display_data and cfg.display_ip is not None and cfg.display_port is not None)
        else cfg.display_compressed_images
    )

    teleop = make_teleoperator_from_config(cfg.teleop)
    robot = make_robot_from_config(cfg.robot)
    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    teleop.connect()
    robot.connect()

    try:
        teleop_loop(
            teleop=teleop,
            robot=robot,
            fps=cfg.fps,
            display_data=cfg.display_data,
            duration=cfg.teleop_time_s,
            teleop_action_processor=teleop_action_processor,
            robot_action_processor=robot_action_processor,
            robot_observation_processor=robot_observation_processor,
            display_compressed_images=display_compressed_images,
        )
    except KeyboardInterrupt:
        pass
    finally:
        if cfg.display_data:
            rr.rerun_shutdown()
        teleop.disconnect()
        robot.disconnect()

def main():
    print("registering plugins...")
    register_third_party_plugins()
    print("parsing...")

    host_port = 4
    left_camera = OpenCVCameraConfig(
        index_or_path=f"/dev/v4l/by-path/pci-0000:c3:00.{host_port}-usb-0:1.1:1.0-video-index0",
        width=640, height=480, fps=30, rotation=Cv2Rotation.ROTATE_180,backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    right_camera = OpenCVCameraConfig(
        index_or_path=f"/dev/v4l/by-path/pci-0000:c3:00.{host_port}-usb-0:1.3:1.0-video-index0",
        width=640, height=480, fps=30, backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    top_camera = OpenCVCameraConfig(
        index_or_path=f"/dev/v4l/by-id/usb-Innomaker_Innomaker-U20CAM-1080p-S1_SN0001-video-index0",
        width=640, height=480, fps=30, backend=Cv2Backends.V4L2,fourcc="MJPG"
    )

    robot = bi_so_follower.BiSOFollowerConfig(
            left_arm_config= so_follower.SO101FollowerConfig(
                port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A056971-if00",
                # cameras= {"wrist":left_camera}

            ),
            right_arm_config= so_follower.SO101FollowerConfig(
                port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7A058163-if00",
                # cameras= {"wrist":right_camera,"top":top_camera}
            ),
            id = "bot",
        )

    cfg= TeleoperateConfig(
        robot = robot,
        teleop = bi_so_leader.BiSOLeaderConfig(
            left_arm_config=so_leader.SO101LeaderConfig(
                port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00"
            ),
            right_arm_config=so_leader.SO101LeaderConfig(
                port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6084492-if00"
            ),
            id = "leader"
        ),
        # display_data=True
    )
    teleoperate(cfg)


if __name__ == "__main__":
    main()