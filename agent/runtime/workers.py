from __future__ import annotations

import logging
import math
import time

import torch

from lerobot.datasets.utils import build_dataset_frame, hw_to_dataset_features
from lerobot.policies.factory import make_pre_post_processors
from lerobot.policies.rtc.latency_tracker import LatencyTracker

from agent.runtime.models import FailureReason

logger = logging.getLogger(__name__)


def policy_infer_loop(runtime, shutdown_event) -> None:
    logger.info("[GET_ACTIONS] Starting get actions thread")
    bundle = runtime.policy_bundle
    action_queue = runtime.action_queue
    robot = runtime.robot_handle
    policy = bundle.policy

    last_inference_timestamp = None
    latency_tracker = LatencyTracker()
    fps = runtime.cfg.fps
    time_per_chunk = 1.0 / fps
    dataset_features = hw_to_dataset_features(robot.observation_features(), "observation")
    policy_device = policy.config.device
    get_actions_threshold = runtime.cfg.action_queue_size_to_get_new_actions
    if not runtime.cfg.rtc.enabled:
        get_actions_threshold = 0

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=bundle.policy_cfg,
        pretrained_path=bundle.pretrained_path,
        dataset_stats=None,
        preprocessor_overrides={
            "device_processor": {"device": bundle.policy_cfg.device},
        },
    )

    while not shutdown_event.is_set() and not runtime.process_shutdown_event.is_set():
        try:
            if action_queue.qsize() > get_actions_threshold:
                time.sleep(0.02)
                continue

            current_time = time.perf_counter()
            action_index_before_inference = action_queue.get_action_index()
            prev_actions = action_queue.get_left_over()

            inference_latency = latency_tracker.max()
            inference_delay = math.ceil(inference_latency / time_per_chunk)
            obs, task = runtime.get_live_observation_for_worker()
            obs_processed = bundle.robot_observation_processor(obs)
            obs_with_policy_features = build_dataset_frame(
                dataset_features,
                obs_processed,
                prefix="observation",
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

            obs_with_policy_features["task"] = [task]
            obs_with_policy_features["robot_type"] = robot.name
            preprocessed_obs = preprocessor(obs_with_policy_features)

            if not runtime.should_take_action():
                continue

            if last_inference_timestamp is not None:
                runtime.inference_dt = time.perf_counter() - last_inference_timestamp
            last_inference_timestamp = time.perf_counter()
            actions = policy.predict_action_chunk(
                preprocessed_obs,
                inference_delay=inference_delay,
                prev_chunk_left_over=prev_actions,
            )

            original_actions = actions.squeeze(0).clone()
            postprocessed_actions = postprocessor(actions).squeeze(0)

            new_latency = time.perf_counter() - current_time
            new_delay = math.ceil(new_latency / time_per_chunk)
            latency_tracker.add(new_latency)

            action_queue.merge(
                original_actions,
                postprocessed_actions,
                new_delay,
                action_index_before_inference,
            )
        except Exception as exc:
            runtime.handle_worker_failure(
                worker_name="policy_infer",
                exc=exc,
                reason=FailureReason.HARDWARE_DISCONNECT,
            )
            return


def actor_control_loop(runtime, shutdown_event) -> None:
    logger.info("[ACTOR] Starting actor thread")
    action_queue = runtime.action_queue
    robot = runtime.robot_handle
    action_count = 0
    action_interval = 1.0 / runtime.cfg.fps

    while not shutdown_event.is_set() and not runtime.process_shutdown_event.is_set():
        if not runtime.should_take_action():
            continue        
        start_time = time.perf_counter()
        try:
            action = action_queue.get()
            if action is not None:
                action = action.cpu()
                action_dict = {key: action[i].item() for i, key in enumerate(robot.action_features())}
                action_processed = runtime.policy_bundle.robot_action_processor((action_dict, None))
                robot.send_action(action_processed)
                runtime.record_action_success()
                action_count += 1
        except Exception as exc:
            runtime.handle_worker_failure(
                worker_name="actor_control",
                exc=exc,
                reason=FailureReason.HARDWARE_DISCONNECT,
            )
            return

        dt_s = time.perf_counter() - start_time
        time.sleep(max(0, (action_interval - dt_s) - 0.001))

    logger.info("[ACTOR] Actor thread shutting down. Total actions executed: %s", action_count)