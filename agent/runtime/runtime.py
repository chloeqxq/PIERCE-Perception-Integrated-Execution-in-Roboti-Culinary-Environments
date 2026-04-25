from __future__ import annotations

import logging
import threading
import time
from threading import Event, Lock, RLock, Thread

from lerobot.policies.rtc.action_queue import ActionQueue

from agent.runtime.models import FailureReason, RuntimeState, RuntimeStatus
from agent.runtime.policy_loader import PolicyBundle, load_policy_bundle
from agent.runtime.robot_ops import connect_robot, disconnect_robot
from agent.runtime.workers import actor_control_loop, policy_infer_loop

logger = logging.getLogger(__name__)


class RobotHandle:
    def __init__(self):
        self.lock = Lock()
        self.robot = None
        self.cached_obs = None
        self.task = ""
        self.take_action = False
        self.base_goal = 0
        self.max_base_angle = 5000
        self.name = ""

    def bind_robot(self, robot) -> None:
        with self.lock:
            self.robot = robot
            self.name = robot.name if hasattr(robot, "name") else ""

    def get_raw_robot(self):
        with self.lock:
            return self.robot

    def get_observation(self):
        with self.lock:
            if self.robot is None:
                raise RuntimeError("Robot not initialized")
            self.cached_obs = self.robot.get_observation()
            return self.cached_obs, self.task

    def get_latest_obs(self):
        with self.lock:
            return self.cached_obs

    def set_task(self, task: str) -> None:
        with self.lock:
            self.task = task

    def get_task(self) -> str:
        with self.lock:
            return self.task

    def allow_action(self, allow: bool) -> None:
        with self.lock:
            self.take_action = allow

    def can_take_action(self) -> bool:
        with self.lock:
            return self.take_action

    def send_action(self, action) -> None:
        with self.lock:
            if self.robot is None:
                raise RuntimeError("Robot not initialized")
            if self.take_action:
                self.robot.send_action(action)

    def observation_features(self):
        with self.lock:
            if self.robot is None:
                raise RuntimeError("Robot not initialized")
            return self.robot.observation_features

    def action_features(self):
        with self.lock:
            if self.robot is None:
                raise RuntimeError("Robot not initialized")
            return self.robot.action_features

    def rotate_base(self, steps: int):
        with self.lock:
            if self.robot is None:
                return False, self.base_goal
            if abs(self.base_goal + steps) >= self.max_base_angle:
                return False, self.base_goal
            self.robot.right_arm.step_base(steps)
            self.base_goal += steps
            return True, self.base_goal

    def get_base_angle(self):
        with self.lock:
            return self.base_goal


class ServiceRuntime:
    def __init__(self, cfg, process_shutdown_event: Event):
        self.cfg = cfg
        self.process_shutdown_event = process_shutdown_event
        self.state_lock = RLock()
        self.lifecycle_lock = Lock()
        self.robot_handle = RobotHandle()
        self.status = RuntimeStatus(current_task=getattr(cfg, "task", ""))
        self.policy_bundle: PolicyBundle | None = None
        self.action_queue = None
        self.worker_shutdown_event = None
        self.get_actions_thread = None
        self.actor_thread = None
        self.operation_thread = None
        self.inference_dt = 1.0
        self.max_reconnect_attempts = 3
        self.reconnect_backoff_seconds = [1.0, 2.0, 5.0]

    def initialize(self) -> None:
        self._set_state(RuntimeState.STARTING, message="Initializing service runtime")
        self.policy_bundle = load_policy_bundle(self.cfg)
        self.status.current_model_path = self.policy_bundle.pretrained_path
        self.connect_robot()
        self.robot_handle.set_task(self.cfg.task)
        self.start_workers()
        self._set_state(RuntimeState.READY, reason=None, message="Service runtime ready")

    def connect_robot(self) -> None:
        robot = connect_robot()
        self.robot_handle.bind_robot(robot)
        try:
            obs, _ = self.robot_handle.get_observation()
            self.record_observation_success(obs, serving_cached=False)
        except Exception as exc:
            logger.warning("Initial observation after robot connect failed: %s", exc)

    def start_workers(self) -> None:
        if self.policy_bundle is None:
            raise RuntimeError("Policy bundle is not loaded")

        self.worker_shutdown_event = Event()
        self.action_queue = ActionQueue(self.cfg.rtc)
        self.get_actions_thread = Thread(
            target=policy_infer_loop,
            args=(self, self.worker_shutdown_event),
            daemon=True,
            name="GetActions",
        )
        self.actor_thread = Thread(
            target=actor_control_loop,
            args=(self, self.worker_shutdown_event),
            daemon=True,
            name="Actor",
        )
        self.get_actions_thread.start()
        self.actor_thread.start()

    def stop_workers(self) -> None:
        if self.worker_shutdown_event is not None:
            self.worker_shutdown_event.set()

        current = threading.current_thread()
        for thread in [self.get_actions_thread, self.actor_thread]:
            if thread and thread.is_alive() and thread is not current:
                thread.join(timeout=5)

        self.get_actions_thread = None
        self.actor_thread = None
        self.worker_shutdown_event = None
        self.action_queue = None

    def shutdown(self) -> None:
        self.process_shutdown_event.set()
        self.stop_workers()
        disconnect_robot(self.robot_handle.get_raw_robot())
        self._set_state(RuntimeState.STOPPED, message="Service runtime stopped")

    def should_take_action(self) -> bool:
        return self.robot_handle.can_take_action()

    def record_observation_success(self, obs, *, serving_cached: bool) -> None:
        now = time.time()
        with self.state_lock:
            self.status.last_successful_observation_time = now
            self.status.serving_cached_observation = serving_cached
            self.status.observation_age_seconds = 0.0 if not serving_cached else self.status.observation_age_seconds
            self.status.current_task = self.robot_handle.get_task()
            self.status.base_angle = self.robot_handle.get_base_angle()

    def record_action_success(self) -> None:
        with self.state_lock:
            self.status.last_successful_action_time = time.time()

    def get_live_observation_for_worker(self):
        obs, task = self.robot_handle.get_observation()
        self.record_observation_success(obs, serving_cached=False)
        return obs, task

    def get_safe_observation(self):
        current_task = self.robot_handle.get_task()
        if self.status.state in {RuntimeState.RECONNECTING, RuntimeState.RELOADING_MODEL}:
            cached = self.robot_handle.get_latest_obs()
            if cached is None:
                return None
            age = self._observation_age_seconds()
            return cached, current_task, {
                "is_stale": True,
                "staleness_seconds": age,
                "message": self.status.message,
            }

        try:
            obs, task = self.robot_handle.get_observation()
            self.record_observation_success(obs, serving_cached=False)
            return obs, task, {"is_stale": False, "staleness_seconds": 0.0, "message": None}
        except Exception as exc:
            logger.warning("Observation request failed, falling back to cache if available: %s", exc)
            self.handle_worker_failure(
                worker_name="api_observation",
                exc=exc,
                reason=FailureReason.HARDWARE_DISCONNECT,
            )
            cached = self.robot_handle.get_latest_obs()
            if cached is None:
                raise
            age = self._observation_age_seconds()
            with self.state_lock:
                self.status.serving_cached_observation = True
                self.status.observation_age_seconds = age
            return cached, current_task, {
                "is_stale": True,
                "staleness_seconds": age,
                "message": str(exc),
            }

    def set_task(self, task: str) -> None:
        self.robot_handle.set_task(task)
        with self.state_lock:
            self.status.current_task = task

    def set_take_action(self, allow: bool) -> dict:
        with self.state_lock:
            state = self.status.state
        if allow and state != RuntimeState.READY:
            self.robot_handle.allow_action(False)
            with self.state_lock:
                self.status.take_action = False
            return {
                "status": "blocked",
                "motors_active": False,
                "reason": state.value,
            }

        self.robot_handle.allow_action(allow)
        with self.state_lock:
            self.status.take_action = allow
        return {"status": "success", "motors_active": allow}

    def rotate_base(self, steps: int) -> dict:
        with self.state_lock:
            state = self.status.state
        if state != RuntimeState.READY:
            return {
                "status": False,
                "base_goal": self.robot_handle.get_base_angle(),
                "reason": state.value,
            }

        try:
            success, base_goal = self.robot_handle.rotate_base(steps)
            with self.state_lock:
                self.status.base_angle = base_goal
            return {"status": success, "base_goal": base_goal}
        except Exception as exc:
            self.handle_worker_failure(
                worker_name="rotate_base",
                exc=exc,
                reason=FailureReason.HARDWARE_DISCONNECT,
            )
            return {
                "status": False,
                "base_goal": self.robot_handle.get_base_angle(),
                "reason": FailureReason.HARDWARE_DISCONNECT.value,
            }

    def get_status_payload(self) -> dict:
        with self.state_lock:
            self.status.current_task = self.robot_handle.get_task()
            self.status.take_action = self.robot_handle.can_take_action()
            self.status.base_angle = self.robot_handle.get_base_angle()
            if self.status.serving_cached_observation:
                self.status.observation_age_seconds = self._observation_age_seconds()
            return self.status.to_dict()

    def request_reconnect(self, *, force: bool = False, reason: str | None = None) -> dict:
        request_reason = reason or FailureReason.OPERATOR_REQUESTED_RECONNECT.value
        if not self.lifecycle_lock.acquire(blocking=False):
            return self._busy_response()

        with self.state_lock:
            self.status.active_operation = "reconnect"
            self.status.reason = request_reason
            self.status.state = RuntimeState.RECONNECTING
            self.status.message = "Reconnect requested"

        self.operation_thread = Thread(
            target=self._run_reconnect,
            args=(request_reason,),
            daemon=True,
            name="ReconnectOperation",
        )
        self.operation_thread.start()
        return {
            "status": "accepted",
            "current_state": RuntimeState.RECONNECTING.value,
            "active_operation": "reconnect",
            "message": "Reconnect started",
        }

    def request_model_reload(self, *, checkpoint_path: str, policy_type: str | None = None) -> dict:
        if not self.lifecycle_lock.acquire(blocking=False):
            return self._busy_response()

        with self.state_lock:
            self.status.active_operation = "reload_model"
            self.status.state = RuntimeState.RELOADING_MODEL
            self.status.reason = FailureReason.OPERATOR_REQUESTED_RELOAD.value
            self.status.pending_model_path = checkpoint_path
            self.status.message = "Model reload requested"

        self.operation_thread = Thread(
            target=self._run_model_reload,
            args=(checkpoint_path, policy_type),
            daemon=True,
            name="ReloadOperation",
        )
        self.operation_thread.start()
        return {
            "status": "accepted",
            "current_state": RuntimeState.RELOADING_MODEL.value,
            "previous_model_path": self.status.current_model_path,
            "requested_model_path": checkpoint_path,
            "active_operation": "reload_model",
            "message": "Model reload started",
        }

    def handle_worker_failure(self, *, worker_name: str, exc: Exception, reason: FailureReason) -> None:
        logger.error("Worker '%s' failed: %s", worker_name, exc, exc_info=True)
        self.robot_handle.allow_action(False)
        with self.state_lock:
            self.status.take_action = False
            self.status.reason = reason.value
            self.status.message = f"{worker_name} failed: {exc}"
            if self.status.state not in {RuntimeState.RECONNECTING, RuntimeState.RELOADING_MODEL, RuntimeState.STOPPED}:
                self.status.state = RuntimeState.DEGRADED

        if reason == FailureReason.HARDWARE_DISCONNECT and not self.process_shutdown_event.is_set():
            self.request_reconnect(reason=reason.value)

    def _run_reconnect(self, reason: str) -> None:
        last_exc = None
        try:
            self.stop_workers()
            disconnect_robot(self.robot_handle.get_raw_robot())
            self.robot_handle.allow_action(False)
            with self.state_lock:
                self.status.take_action = False

            for attempt in range(1, self.max_reconnect_attempts + 1):
                with self.state_lock:
                    self.status.reconnect_attempts = attempt
                    self.status.message = f"Reconnect attempt {attempt}/{self.max_reconnect_attempts}"
                try:
                    self.connect_robot()
                    self.start_workers()
                    self._set_state(
                        RuntimeState.READY,
                        reason=None,
                        message="Reconnect complete; actions remain paused",
                    )
                    return
                except Exception as exc:
                    last_exc = exc
                    logger.warning("Reconnect attempt %s failed: %s", attempt, exc)
                    delay = self.reconnect_backoff_seconds[min(attempt - 1, len(self.reconnect_backoff_seconds) - 1)]
                    time.sleep(delay)

            self._set_state(
                RuntimeState.DEGRADED,
                reason=reason,
                message=f"Reconnect failed: {last_exc}",
            )
        finally:
            with self.state_lock:
                self.status.active_operation = None
            self.lifecycle_lock.release()

    def _run_model_reload(self, checkpoint_path: str, policy_type: str | None) -> None:
        previous_bundle = self.policy_bundle
        try:
            self.stop_workers()
            self.robot_handle.allow_action(False)
            with self.state_lock:
                self.status.take_action = False

            new_bundle = load_policy_bundle(
                self.cfg,
                pretrained_path=checkpoint_path,
                policy_type=policy_type,
            )
            self.policy_bundle = new_bundle
            with self.state_lock:
                self.status.current_model_path = new_bundle.pretrained_path
                self.status.pending_model_path = None
            self.start_workers()
            self._set_state(
                RuntimeState.READY,
                reason=None,
                message="Model reload complete; actions remain paused",
            )
        except Exception as exc:
            logger.error("Model reload failed: %s", exc, exc_info=True)
            self.policy_bundle = previous_bundle
            with self.state_lock:
                self.status.pending_model_path = None
                self.status.reason = FailureReason.INVALID_CHECKPOINT.value
                self.status.message = f"Model reload failed: {exc}"
            if previous_bundle is not None:
                try:
                    self.start_workers()
                    self._set_state(RuntimeState.READY, reason=None, message="Reload failed; previous model restored")
                except Exception as restart_exc:
                    self._set_state(
                        RuntimeState.DEGRADED,
                        reason=FailureReason.POLICY_LOAD_ERROR.value,
                        message=f"Reload rollback failed: {restart_exc}",
                    )
            else:
                self._set_state(
                    RuntimeState.DEGRADED,
                    reason=FailureReason.POLICY_LOAD_ERROR.value,
                    message=f"Model reload failed: {exc}",
                )
        finally:
            with self.state_lock:
                self.status.active_operation = None
            self.lifecycle_lock.release()

    def _set_state(self, state: RuntimeState, *, reason: str | None = None, message: str | None = None) -> None:
        with self.state_lock:
            self.status.state = state
            self.status.reason = reason
            self.status.message = message
            self.status.current_task = self.robot_handle.get_task()
            self.status.take_action = self.robot_handle.can_take_action()
            self.status.base_angle = self.robot_handle.get_base_angle()
            self.status.serving_cached_observation = state in {
                RuntimeState.RECONNECTING,
                RuntimeState.RELOADING_MODEL,
            }
            if self.status.serving_cached_observation:
                self.status.observation_age_seconds = self._observation_age_seconds()

    def _observation_age_seconds(self) -> float | None:
        with self.state_lock:
            if self.status.last_successful_observation_time is None:
                return None
            return max(0.0, time.time() - self.status.last_successful_observation_time)

    def _busy_response(self) -> dict:
        with self.state_lock:
            return {
                "status": "busy",
                "current_state": self.status.state.value,
                "active_operation": self.status.active_operation,
                "message": "Another lifecycle operation is already running",
            }