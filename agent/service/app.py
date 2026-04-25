from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.runtime.api import (
    ActionAllowCommand,
    BaseRotateCommand,
    ReconnectCommand,
    ReloadModelCommand,
    TaskCommand,
)
from agent.runtime.api.routes import (
    get_observation_response,
    get_runtime,
    get_status_response,
    reconnect_response,
    reload_model_response,
    rotate_base_response,
    set_allow_act_response,
    set_task_response,
)

try:
    from lerobot.utils.utils import log_say
except ImportError:
    log_say = None


WEB_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "web_dashboard"
WEB_DASHBOARD_INDEX = WEB_DASHBOARD_DIR / "dashboard.html"


def create_app(runtime) -> FastAPI:
    app = FastAPI(title="VLA Orchestration API")
    app.state.runtime = runtime

    @app.get("/observation")
    def api_get_observation():
        return get_observation_response(get_runtime(app))

    @app.post("/task")
    def api_set_task(cmd: TaskCommand):
        if log_say is not None:
            log_say(f"updating task to: {cmd.task}")
        return set_task_response(get_runtime(app), cmd.task)

    @app.post("/allow_act")
    def api_allow_act(cmd: ActionAllowCommand):
        return set_allow_act_response(get_runtime(app), cmd.allow_act)

    @app.post("/base")
    def api_base_rotate(cmd: BaseRotateCommand):
        return rotate_base_response(get_runtime(app), cmd.steps)

    @app.get("/status")
    def api_get_status():
        return get_status_response(get_runtime(app))

    @app.post("/reconnect")
    def api_reconnect(cmd: ReconnectCommand):
        return reconnect_response(get_runtime(app), force=cmd.force, reason=cmd.reason)

    @app.post("/reload_model")
    def api_reload_model(cmd: ReloadModelCommand):
        return reload_model_response(
            get_runtime(app),
            checkpoint_path=cmd.checkpoint_path,
            policy_type=cmd.policy_type,
        )

    if WEB_DASHBOARD_INDEX.exists():
        @app.get("/", include_in_schema=False)
        def dashboard_root():
            return FileResponse(WEB_DASHBOARD_INDEX)

        @app.get("/dashboard", include_in_schema=False)
        def dashboard_index():
            return FileResponse(WEB_DASHBOARD_INDEX)

        @app.get("/dashboard/", include_in_schema=False)
        def dashboard_index_slash():
            return FileResponse(WEB_DASHBOARD_INDEX)

    if WEB_DASHBOARD_DIR.exists():
        app.mount("/dashboard", StaticFiles(directory=WEB_DASHBOARD_DIR), name="dashboard")

    return app
