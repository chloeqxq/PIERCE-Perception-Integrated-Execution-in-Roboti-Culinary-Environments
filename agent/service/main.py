from __future__ import annotations

import logging

import uvicorn
from lerobot.configs import parser
from lerobot.rl.process import ProcessSignalHandler
from lerobot.utils.utils import init_logging, log_say

from agent.runtime import ServiceRuntime
from agent.service.app import create_app
from agent.service.config import RobotServiceConfig

logger = logging.getLogger(__name__)


def run_service(cfg: RobotServiceConfig) -> None:
    init_logging()
    logger.info("Using device: %s", cfg.device)

    signal_handler = ProcessSignalHandler(use_threads=True, display_pid=False)
    runtime = ServiceRuntime(cfg, signal_handler.shutdown_event)

    try:
        runtime.initialize()
        app = create_app(runtime)
        logger.info("Starting VLA Control Server on port 8000...")
        log_say("robot server initialization complete")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    finally:
        runtime.shutdown()
        logger.info("Cleanup completed")


def main(cfg: RobotServiceConfig):
    run_service(cfg)


if __name__ == "__main__":
    cfg = RobotServiceConfig(

    )
    main(cfg)
