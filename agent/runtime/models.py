from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    RELOADING_MODEL = "reloading_model"
    STOPPED = "stopped"


class FailureReason(str, Enum):
    HARDWARE_DISCONNECT = "hardware_disconnect"
    CAMERA_FAILURE = "camera_failure"
    WORKER_CRASH = "worker_crash"
    POLICY_LOAD_ERROR = "policy_load_error"
    INVALID_CHECKPOINT = "invalid_checkpoint"
    OPERATOR_REQUESTED_RECONNECT = "operator_requested_reconnect"
    OPERATOR_REQUESTED_RELOAD = "operator_requested_reload"
    UNKNOWN = "unknown"


@dataclass
class RuntimeStatus:
    state: RuntimeState = RuntimeState.STARTING
    reason: str | None = None
    message: str | None = None
    active_operation: str | None = None
    current_model_path: str | None = None
    pending_model_path: str | None = None
    current_task: str = ""
    take_action: bool = False
    reconnect_attempts: int = 0
    last_successful_observation_time: float | None = None
    last_successful_action_time: float | None = None
    serving_cached_observation: bool = False
    observation_age_seconds: float | None = None
    base_angle: int | float | None = None
    capabilities: dict[str, bool] = field(
        default_factory=lambda: {"reconnect": True, "reload_model": True}
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reason": self.reason,
            "message": self.message,
            "active_operation": self.active_operation,
            "current_model_path": self.current_model_path,
            "pending_model_path": self.pending_model_path,
            "current_task": self.current_task,
            "take_action": self.take_action,
            "reconnect_attempts": self.reconnect_attempts,
            "last_successful_observation_time": self.last_successful_observation_time,
            "last_successful_action_time": self.last_successful_action_time,
            "serving_cached_observation": self.serving_cached_observation,
            "observation_age_seconds": self.observation_age_seconds,
            "base_angle": self.base_angle,
            "capabilities": self.capabilities,
        }