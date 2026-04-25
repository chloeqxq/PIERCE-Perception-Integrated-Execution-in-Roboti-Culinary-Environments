from __future__ import annotations

import logging

from agent.hardware import get_robot
from lerobot.robots.utils import make_robot_from_config
from lerobot.utils.utils import log_say

logger = logging.getLogger(__name__)


def connect_robot():
    robot_cfg = get_robot()
    logger.info("Initializing robot %s", robot_cfg.type)
    robot = make_robot_from_config(robot_cfg)
    robot.connect(calibrate=False)
    configure_robot_after_connect(robot)
    log_say("robot connected")
    return robot


def configure_robot_after_connect(robot) -> None:
    if hasattr(robot, "right_arm") and hasattr(robot.right_arm, "config_base"):
        robot.right_arm.config_base()


def disconnect_robot(robot) -> None:
    if robot is None:
        return

    try:
        robot.disconnect()
    except Exception as exc:
        logger.warning("Robot disconnect raised an exception: %s", exc)