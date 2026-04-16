import time
import torch
import logging

from lerobot.processor.pipeline import ProcessorStep
from lerobot.types import EnvTransition
from lerobot.configs.types import PipelineFeatureType, PolicyFeature


class SkewerActionProcessor(ProcessorStep):
    """
    Dedicated action processor (state machine) for the skewer task.
    This step is mounted to teleop_action_processor and modifies teleop actions
    before they are sent to the robot.
    """

    TELEOP_PICK = "TELEOP_PICK"
    AUTO_ALIGN = "AUTO_ALIGN"
    GRIPPER_CLOSE_THRESHOLD = 0.1

    def __init__(self):
        super().__init__()

        # Left arm stays fixed to hold the skewer.
        self.LEFT_ARM_FIXED_POSE = torch.tensor([0.0, -0.5, 0.3, 1.2, 0.0, 0.0])  # TODO: Replace with actual values.
        # Right arm moves to this pose after a successful pick.
        self.RIGHT_ARM_ALIGN_POSE = torch.tensor([-0.2, 0.4, -0.1, -1.0, 0.0, 1.0])  # TODO: Replace with actual values.
        # Increase this if motion is too fast.
        self.AUTO_ALIGN_DURATION = 2.0

        # Expected 5+1 joint order for named-key action dicts.
        self._joint_order = (
            "shoulder_pan.pos",
            "shoulder_lift.pos",
            "elbow_flex.pos",
            "wrist_flex.pos",
            "wrist_roll.pos",
            "gripper.pos",
        )

        self.state = self.TELEOP_PICK
        self.align_start_time = 0.0
        self.right_arm_start_pose: torch.Tensor | None = None

        logging.info("Skewer Processor initialized. Current state: TELEOP_PICK")

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        action_dict = transition.action
        if not isinstance(action_dict, dict):
            logging.error(f"Expected action dict but got: {type(action_dict)}")
            return transition

        # Check 1 & 2: in bi_so setup we expect named keys, not a flat "action" tensor.
        if "action" in action_dict:
            logging.error(
                "Unexpected flat action format for bi_so setup. "
                "Expected keys like left_shoulder_pan.pos / right_gripper.pos."
            )
            return transition

        self._process_named_keys(action_dict)

        transition.action = action_dict
        return transition

    def _process_named_keys(self, action_dict: dict) -> None:
        left_keys = [f"left_{joint}" for joint in self._joint_order]
        right_keys = [f"right_{joint}" for joint in self._joint_order]
        expected = left_keys + right_keys

        missing = [k for k in expected if k not in action_dict]
        if missing:
            logging.error(
                "Named-key action format mismatch. "
                f"Missing keys: {missing[:4]}{'...' if len(missing) > 4 else ''}. "
                f"Available keys sample: {list(action_dict.keys())[:8]}"
            )
            return

        # Keep left arm fixed on every frame.
        for i, key in enumerate(left_keys):
            action_dict[key] = float(self.LEFT_ARM_FIXED_POSE[i].item())

        if self.state == self.TELEOP_PICK:
            # Check 3a/3b: this uses right_gripper.pos and assumes closed value is small.
            right_gripper_val = float(action_dict["right_gripper.pos"])
            if right_gripper_val < self.GRIPPER_CLOSE_THRESHOLD:
                start_pose = torch.tensor([float(action_dict[k]) for k in right_keys], dtype=torch.float32)
                self._enter_auto_align(start_pose)
        elif self.state == self.AUTO_ALIGN:
            target = self._compute_auto_align_target()
            if target is None:
                return
            for i, key in enumerate(right_keys):
                action_dict[key] = float(target[i].item())

    def _enter_auto_align(self, start_pose: torch.Tensor) -> None:
        # Start a timed interpolation from current right pose to align pose.
        self.state = self.AUTO_ALIGN
        self.align_start_time = time.perf_counter()
        self.right_arm_start_pose = start_pose

    def _compute_auto_align_target(self) -> torch.Tensor | None:
        # Compute one interpolation step for AUTO_ALIGN state.
        if self.right_arm_start_pose is None:
            self.state = self.TELEOP_PICK
            return None

        progress = (time.perf_counter() - self.align_start_time) / self.AUTO_ALIGN_DURATION
        progress = max(0.0, min(1.0, progress))
        target = self.right_arm_start_pose + (self.RIGHT_ARM_ALIGN_POSE - self.right_arm_start_pose) * progress

        if progress >= 1.0:
            logging.info("Alignment complete. Returning to TELEOP_PICK.")
            self.state = self.TELEOP_PICK

        return target

    def transform_features(
        self, features: dict[PipelineFeatureType, dict[str, PolicyFeature]]
    ) -> dict[PipelineFeatureType, dict[str, PolicyFeature]]:
        return features
