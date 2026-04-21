#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
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

import logging
import math
import sys
import time
import traceback
from dataclasses import dataclass, field
from threading import Event, Lock, Thread

import torch
from torch import Tensor

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig  # noqa: F401
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig  # noqa: F401
from lerobot.configs import parser
from lerobot.configs.policies import PreTrainedConfig
from lerobot.configs.types import RTCAttentionSchedule
from lerobot.datasets.utils import build_dataset_frame, hw_to_dataset_features
from lerobot.policies.factory import get_policy_class, make_pre_post_processors
from lerobot.policies.rtc.action_queue import ActionQueue
from lerobot.policies.rtc.configuration_rtc import RTCConfig
from lerobot.policies.rtc.latency_tracker import LatencyTracker
from lerobot.processor.factory import (
    make_default_robot_action_processor,
    make_default_robot_observation_processor,
)
from lerobot.rl.process import ProcessSignalHandler
from lerobot.robots import (  # noqa: F401
    Robot,
    RobotConfig,
    bi_so_follower,
    koch_follower,
    robot,
    so_follower,
)
from lerobot.robots.utils import make_robot_from_config
from lerobot.utils.constants import OBS_IMAGES
from lerobot.utils.hub import HubMixin
from lerobot.utils.utils import init_logging,log_say

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from hardware import get_robot
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import base64
import cv2
import numpy as np
import torch
'''
Thread Safe wrapper for operating the robot
'''
class RobotWrapper:
    def __init__(self, robot: Robot):
        self.robot:bi_so_follower.BiSOFollower= robot
        self.lock = Lock()
        self.cached_obs = None
        self.task = ""
        self.take_action = False
        self.base_goal = 0
        self.max_base_angle = 2000

    def get_observation(self) -> dict[str, Tensor]:
        with self.lock:
            self.cached_obs = self.robot.get_observation()
            return self.cached_obs,self.task

    def allow_action(self,allow):
        with self.lock:
            self.take_action = allow

    def send_action(self, action: dict[str, float]) -> None:
        with self.lock:
            # pass
            if self.take_action:
            # logger.info(action)
                self.robot.send_action(action)

    def observation_features(self) -> list[str]:
        with self.lock:
            return self.robot.observation_features

    def action_features(self) -> list[str]:
        with self.lock:
            return self.robot.action_features

    def get_latest_obs(self):
        with self.lock:
            return self.cached_obs
    
    def set_task(self,task):
        with self.lock:
            self.task = task
            # log_say(f"task updated to: {task}")
    
    def rotate_base(self,steps):
        with self.lock:
            if(abs(self.base_goal+steps)<self.max_base_angle):
                self.robot.right_arm.step_base(steps)
                self.base_goal+=steps
                return True,self.base_goal
                # log_say(f"rotating base by {steps} steps")
            else:
                return False,self.base_goal

    def get_base_angle(self):
        with self.lock:
            return self.base_goal

@dataclass
class RobotConfig(HubMixin):
    """Configuration for RTC demo with action chunking policies and real robots."""

    # Policy configuration
    policy: PreTrainedConfig | None = None

    # Robot configuration
    robot: RobotConfig | None = None

    # RTC configuration
    rtc: RTCConfig = field(
        default_factory=lambda: RTCConfig(
            execution_horizon=10,
            max_guidance_weight=1.0,
            prefix_attention_schedule=RTCAttentionSchedule.EXP,
        )
    )

    # Demo parameters
    duration: float = 30.0  # Duration to run the demo (seconds)
    fps: float = 10.0  # Action execution frequency (Hz)

    # Compute device
    device: str | None = None  # Device to run on (cuda, cpu, auto)

    # Get new actions horizon. The amount of executed steps after which will be requested new actions.
    # It should be higher than inference delay + execution horizon.
    action_queue_size_to_get_new_actions: int = 30

    # Task to execute
    task: str = field(default="", metadata={"help": "Task to execute"})

    # Torch compile configuration
    use_torch_compile: bool = field(
        default=False,
        metadata={"help": "Use torch.compile for faster inference (PyTorch 2.0+)"},
    )

    torch_compile_backend: str = field(
        default="inductor",
        metadata={"help": "Backend for torch.compile (inductor, aot_eager, cudagraphs)"},
    )

    torch_compile_mode: str = field(
        default="default",
        metadata={"help": "Compilation mode (default, reduce-overhead, max-autotune)"},
    )

    torch_compile_disable_cudagraphs: bool = field(
        default=True,
        metadata={
            "help": "Disable CUDA graphs in torch.compile. Required due to in-place tensor "
            "operations in denoising loop (x_t += dt * v_t) which cause tensor aliasing issues."
        },
    )

    def __post_init__(self):
        # HACK: We parse again the cli args here to get the pretrained path if there was one.
        # # Validate that robot configuration is provided
        # if self.robot is None:
        #     raise ValueError("Robot configuration must be provided")
        pass

    @classmethod
    def __get_path_fields__(cls) -> list[str]:
        """This enables the parser to load config from the policy using `--policy.path=local/dir`"""
        return ["policy"]


def is_image_key(k: str) -> bool:
    return k.startswith(OBS_IMAGES)


def policy_infer(
    policy,
    robot: RobotWrapper,
    robot_observation_processor,
    action_queue: ActionQueue,
    shutdown_event: Event,
    cfg: RTCConfig,
):
    """Thread function to request action chunks from the policy.

    Args:
        policy: The policy instance (SmolVLA, Pi0, etc.)
        robot: The robot instance for getting observations
        robot_observation_processor: Processor for raw robot observations
        action_queue: Queue to put new action chunks
        shutdown_event: Event to signal shutdown
        cfg: Demo configuration
    """
    try:
        logger.info("[GET_ACTIONS] Starting get actions thread")

        latency_tracker = LatencyTracker()  # Track latency of action chunks
        fps = cfg.fps
        time_per_chunk = 1.0 / fps

        dataset_features = hw_to_dataset_features(robot.observation_features(), "observation")
        policy_device = policy.config.device

        # Load preprocessor and postprocessor from pretrained files
        # The stats are embedded in the processor .safetensors files
        logger.info(f"[GET_ACTIONS] Loading preprocessor/postprocessor from {cfg.policy.pretrained_path}")

        preprocessor, postprocessor = make_pre_post_processors(
            policy_cfg=cfg.policy,
            pretrained_path=cfg.policy.pretrained_path,
            dataset_stats=None,  # Will load from pretrained processor files
            preprocessor_overrides={
                "device_processor": {"device": cfg.policy.device},
            },
        )

        logger.info("[GET_ACTIONS] Preprocessor/postprocessor loaded successfully with embedded stats")

        get_actions_threshold = cfg.action_queue_size_to_get_new_actions

        if not cfg.rtc.enabled:
            get_actions_threshold = 0

        while not shutdown_event.is_set():
            if action_queue.qsize() <= get_actions_threshold:
                current_time = time.perf_counter()
                action_index_before_inference = action_queue.get_action_index()
                prev_actions = action_queue.get_left_over()

                inference_latency = latency_tracker.max()
                inference_delay = math.ceil(inference_latency / time_per_chunk)
                obs,task = robot.get_observation()
  
                # Apply robot observation processor
                obs_processed = robot_observation_processor(obs)

                obs_with_policy_features = build_dataset_frame(
                    dataset_features, obs_processed, prefix="observation"
                )

                for name in obs_with_policy_features:
                    obs_with_policy_features[name] = torch.from_numpy(obs_with_policy_features[name])
                    if "image" in name:
                        obs_with_policy_features[name] = (
                            obs_with_policy_features[name].type(torch.float32) / 255
                        )
                        obs_with_policy_features[name] = (
                            obs_with_policy_features[name].permute(2, 0, 1).contiguous()
                        )
                    obs_with_policy_features[name] = obs_with_policy_features[name].unsqueeze(0)
                    obs_with_policy_features[name] = obs_with_policy_features[name].to(policy_device)

                obs_with_policy_features["task"] = [task]  # Task should be a list, not a string!
                obs_with_policy_features["robot_type"] = (
                    robot.robot.name if hasattr(robot.robot, "name") else ""
                )

                preproceseded_obs = preprocessor(obs_with_policy_features)
                # Generate actions WITH RTC
                if robot.take_action:
                    actions = policy.predict_action_chunk(
                        preproceseded_obs,
                        inference_delay=inference_delay,
                        prev_chunk_left_over=prev_actions,
                    )

                    # Store original actions (before postprocessing) for RTC
                    original_actions = actions.squeeze(0).clone()

                    postprocessed_actions = postprocessor(actions)

                    postprocessed_actions = postprocessed_actions.squeeze(0)

                    new_latency = time.perf_counter() - current_time
                    new_delay = math.ceil(new_latency / time_per_chunk)
                    latency_tracker.add(new_latency)

                    if cfg.action_queue_size_to_get_new_actions < cfg.rtc.execution_horizon + new_delay:
                        logger.warning(
                            "[GET_ACTIONS] cfg.action_queue_size_to_get_new_actions Too small, It should be higher than inference delay + execution horizon."
                        )

                    action_queue.merge(
                        original_actions, postprocessed_actions, new_delay, action_index_before_inference
                    )
            else:
                # Small sleep to prevent busy waiting
                time.sleep(0.1)

        logger.info("[GET_ACTIONS] get actions thread shutting down")
    except Exception as e:
        logger.error(f"[GET_ACTIONS] Fatal exception in get_actions thread: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


def actor_control(
    robot: RobotWrapper,
    robot_action_processor,
    action_queue: ActionQueue,
    shutdown_event: Event,
    cfg: RTCConfig,
):
    """Thread function to execute actions on the robot.

    Args:
        robot: The robot instance
        action_queue: Queue to get actions from
        shutdown_event: Event to signal shutdown
        cfg: Demo configuration
    """
    try:
        logger.info("[ACTOR] Starting actor thread")

        action_count = 0
        action_interval = 1.0 / cfg.fps

        while not shutdown_event.is_set():
            start_time = time.perf_counter()

            # Try to get an action from the queue with timeout
            action = action_queue.get()

            if action is not None:
                action = action.cpu()
                action_dict = {key: action[i].item() for i, key in enumerate(robot.action_features())}
                action_processed = robot_action_processor((action_dict, None))
                robot.send_action(action_processed)

                action_count += 1

            dt_s = time.perf_counter() - start_time
            time.sleep(max(0, (action_interval - dt_s) - 0.001))

        logger.info(f"[ACTOR] Actor thread shutting down. Total actions executed: {action_count}")
    except Exception as e:
        logger.error(f"[ACTOR] Fatal exception in actor_control thread: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


def _apply_torch_compile(policy, cfg: RobotConfig):
    """Apply torch.compile to the policy's predict_action_chunk method.

    Args:
        policy: Policy instance to compile
        cfg: Configuration containing torch compile settings

    Returns:
        Policy with compiled predict_action_chunk method
    """

    # PI models handle their own compilation
    if policy.type == "pi05" or policy.type == "pi0":
        return policy

    try:
        # Check if torch.compile is available (PyTorch 2.0+)
        if not hasattr(torch, "compile"):
            logger.warning(
                f"torch.compile is not available. Requires PyTorch 2.0+. "
                f"Current version: {torch.__version__}. Skipping compilation."
            )
            return policy

        logger.info("Applying torch.compile to predict_action_chunk...")
        logger.info(f"  Backend: {cfg.torch_compile_backend}")
        logger.info(f"  Mode: {cfg.torch_compile_mode}")
        logger.info(f"  Disable CUDA graphs: {cfg.torch_compile_disable_cudagraphs}")

        # Compile the predict_action_chunk method
        # - CUDA graphs disabled to prevent tensor aliasing from in-place ops (x_t += dt * v_t)
        compile_kwargs = {
            "backend": cfg.torch_compile_backend,
            "mode": cfg.torch_compile_mode,
        }

        # Disable CUDA graphs if requested (prevents tensor aliasing issues)
        if cfg.torch_compile_disable_cudagraphs:
            compile_kwargs["options"] = {"triton.cudagraphs": False}

        original_method = policy.predict_action_chunk
        compiled_method = torch.compile(original_method, **compile_kwargs)
        policy.predict_action_chunk = compiled_method
        logger.info("✓ Successfully compiled predict_action_chunk")

    except Exception as e:
        logger.error(f"Failed to apply torch.compile: {e}")
        logger.warning("Continuing without torch.compile")

    return policy



app = FastAPI(title="VLA Orchestration API")

def rtc_main(cfg: RTCConfig):
    """Main entry point for RTC demo with draccus configuration."""

    # Initialize logging
    init_logging()

    logger.info(f"Using device: {cfg.device}")

    # Setup signal handler for graceful shutdown
    signal_handler = ProcessSignalHandler(use_threads=True, display_pid=False)
    shutdown_event = signal_handler.shutdown_event

    policy = None
    robot = None
    get_actions_thread = None
    actor_thread = None

    policy_class = get_policy_class(cfg.policy.type)

    # Load config and set compile_model for pi0/pi05 models
    config = PreTrainedConfig.from_pretrained(cfg.policy.pretrained_path)

    if cfg.policy.type == "pi05" or cfg.policy.type == "pi0":
        config.compile_model = cfg.use_torch_compile

    if config.use_peft:
        from peft import PeftConfig, PeftModel

        peft_pretrained_path = cfg.policy.pretrained_path
        peft_config = PeftConfig.from_pretrained(peft_pretrained_path)

        policy = policy_class.from_pretrained(
            pretrained_name_or_path=peft_config.base_model_name_or_path, config=config
        )
        policy = PeftModel.from_pretrained(policy, peft_pretrained_path, config=peft_config)
    else:
        policy = policy_class.from_pretrained(cfg.policy.pretrained_path, config=config)

    # Turn on RTC
    policy.config.rtc_config = cfg.rtc

    # Init RTC processort, as by default if RTC disabled in the config
    # The processor won't be created
    policy.init_rtc_processor()

    assert policy.name in ["smolvla", "pi05", "pi0"], "Only smolvla, pi05, and pi0 are supported for RTC"

    policy = policy.to(cfg.device)
    policy.eval()

    # Apply torch.compile to predict_action_chunk method if enabled
    if cfg.use_torch_compile:
        policy = _apply_torch_compile(policy, cfg)

    # Create robot
    robot_cfg = get_robot()
    logger.info(f"Initializing robot {robot_cfg.type}")
    robot:bi_so_follower.BiSOFollower = make_robot_from_config(robot_cfg)
    robot.connect()
    robot.right_arm.config_base() # hack: setup rotating base motor connected to bus of right arm
    robot_wrapper = RobotWrapper(robot)
    robot_wrapper.set_task(cfg.task)

    # Create robot observation processor
    robot_observation_processor = make_default_robot_observation_processor()
    robot_action_processor = make_default_robot_action_processor()

    # Create action queue for communication between threads
    action_queue = ActionQueue(cfg.rtc)

    # Start chunk requester thread
    get_actions_thread = Thread(
        target=policy_infer,
        args=(policy, robot_wrapper, robot_observation_processor, action_queue, shutdown_event, cfg),
        daemon=True,
        name="GetActions",
    )
    get_actions_thread.start()
    logger.info("Started get actions thread")

    # Start action executor thread
    actor_thread = Thread(
        target=actor_control,
        args=(robot_wrapper, robot_action_processor, action_queue, shutdown_event, cfg),
        daemon=True,
        name="Actor",
    )
    actor_thread.start()
    logger.info("Started actor thread")

    logger.info("Started stop by duration thread")

    # Main thread monitors for duration or shutdown
    logger.info(f"Running demo for {cfg.duration} seconds...")
    start_time = time.time()

    app.state.robot_wrapper = robot_wrapper

    logger.info("Starting VLA Control Server on port 8000...")
    try:
        # Blocks the main thread and serves requests
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")

    logger.info("Demo duration reached or shutdown requested")

    # Signal shutdown
    shutdown_event.set()

    # Wait for threads to finish
    if get_actions_thread and get_actions_thread.is_alive():
        logger.info("Waiting for chunk requester thread to finish...")
        get_actions_thread.join()

    if actor_thread and actor_thread.is_alive():
        logger.info("Waiting for action executor thread to finish...")
        actor_thread.join()

    # Cleanup robot
    if robot:
        robot.disconnect()
        logger.info("Robot disconnected")

    logger.info("Cleanup completed")

# Schemas
class TaskCommand(BaseModel):
    task: str

class ActionAllowCommand(BaseModel):
    allow_act: bool

class BaseRotateCommand(BaseModel):
    steps: int

# Hardcoded keys for you to fill in later
IMAGE_KEYS = [
    "right_top",
    "left_wrist",
    "right_wrist",
]


def process_obs_for_agent(obs: dict) -> dict:
    """Extracts named motor states and converts multiple camera arrays to base64."""
    payload = {
        "motor_angles": {},
        "images_base64": {}
    }
    
    # 2. Extract and Encode Multiple Images
    for key in obs.keys():
        if key in IMAGE_KEYS:
            image_data = obs.get(key)
            if image_data is not None:
                if torch.is_tensor(image_data):
                    img_np = image_data.cpu().numpy()
                else:
                    img_np = np.array(image_data)
                # print(img_np.shape)
                # PyTorch images are often (Channels, Height, Width). OpenCV needs (H, W, C).
                if len(img_np.shape) == 3 and img_np.shape[0] in [1, 3]:
                    img_np = np.transpose(img_np, (1, 2, 0))
                    
                # Ensure it's uint8 for encoding
                if img_np.dtype != np.uint8:
                    if img_np.max() <= 1.0:
                        img_np = (img_np * 255).astype(np.uint8)
                    else:
                        img_np = img_np.astype(np.uint8)

                # Convert RGB to BGR for cv2 encoding
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                _, buffer = cv2.imencode('.jpg', img_bgr)
                
                # Append to the nested image dictionary
                payload["images_base64"][key] = base64.b64encode(buffer).decode('utf-8')
        else:
            # 1. Extract Motor Angles (Named Dictionary Values)
            val = obs.get(key)
            if val is not None:
                if torch.is_tensor(val):
                    # .tolist() safely handles both scalars and 1D tensors
                    payload["motor_angles"][key] = val.cpu().numpy().tolist()
                else:
                    payload["motor_angles"][key] = np.array(val).tolist()

    return payload

@app.get("/observation")
def api_get_observation():
    # Safely access the injected robot wrapper
    robot = getattr(app.state, "robot_wrapper", None)
    if not robot:
        raise HTTPException(status_code=500, detail="Robot not initialized.")
    
    obs_dict, current_task = robot.get_observation()
    if not obs_dict:
        raise HTTPException(status_code=404, detail="No observation available.")
    
    # Use our helper function
    agent_payload = process_obs_for_agent(obs_dict)
    agent_payload["current_task"] = current_task
    
    return agent_payload

@app.post("/task")
def api_set_task(cmd: TaskCommand):
    robot = getattr(app.state, "robot_wrapper", None)
    if not robot:
         raise HTTPException(status_code=500)
    robot.set_task(cmd.task)
    return {"status": "success", "task": cmd.task}

@app.post("/allow_act")
def api_allow_act(cmd: ActionAllowCommand):
    robot:RobotWrapper = getattr(app.state, "robot_wrapper", None)
    if not robot:
        raise HTTPException(status_code=500)
    robot.allow_action(cmd.allow_act)
    return {"status": "success", "motors_active": cmd.allow_act}

@app.post("/base")
def api_base_rotate(cmd: BaseRotateCommand):
    robot:RobotWrapper = getattr(app.state, "robot_wrapper", None)
    if not robot:
        raise HTTPException(status_code=500)
    success,base_goal = robot.rotate_base(cmd.steps)
    return {"status":success,"base_goal":base_goal}

from lerobot.policies import SmolVLAConfig,PI05Config

if __name__ == "__main__":
    rtc_main(RobotConfig(
        # policy = SmolVLAConfig(pretrained_path="/home/guff/PIERCE-Perception-Integrated-Execution-in-Roboti-Culinary-Environments/outputs/train/smol_pretrain_targeted/checkpoints/100000/pretrained_model"),
        policy = SmolVLAConfig(pretrained_path="Aasdfip/smolvla_pretrain_curated"),

        # policy = PI05Config(pretrained_path="Aasdfip/pi05_pretrain_14k"),
    
        rtc = RTCConfig(
            enabled=True,execution_horizon=10, max_guidance_weight=2.0,
            # prefix_attention_schedule=RTCAttentionSchedule.EXP
        ),
        fps=30,
        action_queue_size_to_get_new_actions=15,
        duration=3600,
        task="make a foam ball skewer",
        # task="stay still and do nothing",

    ))
    logging.info("RTC finished")
