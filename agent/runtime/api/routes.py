from __future__ import annotations

from fastapi import HTTPException

from agent.runtime.observation import build_observation_payload


def get_runtime(app):
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=500, detail="Service runtime not initialized.")
    return runtime


def get_observation_response(runtime):
    observation = runtime.get_safe_observation()
    if observation is None:
        raise HTTPException(status_code=404, detail="No observation available.")

    obs_dict, current_task, metadata = observation
    if not obs_dict:
        raise HTTPException(status_code=404, detail="No observation available.")

    return build_observation_payload(
        obs_dict,
        current_task,
        is_stale=metadata.get("is_stale", False),
        staleness_seconds=metadata.get("staleness_seconds"),
        message=metadata.get("message"),
    )


def set_task_response(runtime, task: str):
    runtime.set_task(task)
    return {"status": "success", "task": task}


def set_allow_act_response(runtime, allow_act: bool):
    return runtime.set_take_action(allow_act)


def rotate_base_response(runtime, steps: int):
    return runtime.rotate_base(steps)


def get_status_response(runtime):
    return runtime.get_status_payload()


def reconnect_response(runtime, *, force: bool, reason: str | None):
    return runtime.request_reconnect(force=force, reason=reason)


def reload_model_response(runtime, *, checkpoint_path: str, policy_type: str | None):
    return runtime.request_model_reload(checkpoint_path=checkpoint_path, policy_type=policy_type)