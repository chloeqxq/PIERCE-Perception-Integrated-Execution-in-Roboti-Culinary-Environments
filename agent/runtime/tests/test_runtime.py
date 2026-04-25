from __future__ import annotations

from threading import Event

import pytest

from agent.runtime.models import RuntimeState
from agent.runtime.runtime import ServiceRuntime
from agent.runtime import runtime as runtime_module


class DummyPolicyCfg:
    type = "smolvla"
    pretrained_path = "initial-checkpoint"
    device = "cpu"


class DummyRtcCfg:
    enabled = True


class DummyConfig:
    policy = DummyPolicyCfg()
    rtc = DummyRtcCfg()
    fps = 30
    action_queue_size_to_get_new_actions = 2
    duration = 10
    task = "demo task"
    device = "cpu"
    use_torch_compile = False
    torch_compile_backend = "inductor"
    torch_compile_mode = "default"
    torch_compile_disable_cudagraphs = True


class FakeRobot:
    name = "fake-robot"
    observation_features = {"left_wrist": object}
    action_features = {"left_joint": object}

    def __init__(self):
        self.right_arm = self

    def get_observation(self):
        return {"left_joint": [1.0], "left_wrist": [[[0, 0, 0]]], "right_top": [[[0, 0, 0]]]}

    def send_action(self, action):
        return action

    def step_base(self, steps):
        return steps

    def disconnect(self):
        return None


class FakeBundle:
    pretrained_path = "initial-checkpoint"
    policy_type = "smolvla"
    policy_cfg = DummyPolicyCfg()
    policy = object()
    robot_observation_processor = staticmethod(lambda obs: obs)
    robot_action_processor = staticmethod(lambda pair: pair[0])


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(runtime_module, "load_policy_bundle", lambda cfg, **kwargs: FakeBundle())
    monkeypatch.setattr(runtime_module, "connect_robot", lambda: FakeRobot())
    monkeypatch.setattr(ServiceRuntime, "start_workers", lambda self: None)
    monkeypatch.setattr(ServiceRuntime, "stop_workers", lambda self: None)
    service_runtime = ServiceRuntime(DummyConfig(), Event())
    service_runtime.initialize()
    return service_runtime


def test_initialize_sets_ready(runtime):
    status = runtime.get_status_payload()
    assert status["state"] == RuntimeState.READY.value
    assert status["current_task"] == "demo task"


def test_allow_act_respects_ready_state(runtime):
    response = runtime.set_take_action(True)
    assert response == {"status": "success", "motors_active": True}

    runtime._set_state(RuntimeState.DEGRADED, reason="hardware_disconnect", message="degraded")
    blocked = runtime.set_take_action(True)
    assert blocked["status"] == "blocked"
    assert blocked["motors_active"] is False


def test_reload_rejected_when_busy(runtime):
    runtime.lifecycle_lock.acquire()
    try:
        response = runtime.request_model_reload(checkpoint_path="next-checkpoint", policy_type=None)
        assert response["status"] == "busy"
    finally:
        runtime.lifecycle_lock.release()