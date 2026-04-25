from __future__ import annotations

from dataclasses import dataclass, field

from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies import SmolVLAConfig
from lerobot.policies.rtc.configuration_rtc import RTCConfig
from lerobot.utils.hub import HubMixin


@dataclass
class RobotServiceConfig(HubMixin):
    """Configuration for the research robot service runtime."""

    policy: PreTrainedConfig = field(
        default_factory=lambda: SmolVLAConfig(pretrained_path="Aasdfip/smol_adapt_50k")
    )
    rtc: RTCConfig = field(
        default_factory=lambda: RTCConfig(
            enabled=True,
            execution_horizon=10,
            max_guidance_weight=10.0,
        )
    )
    duration: float = 3600.0
    fps: float = 30.0
    device: str | None = None
    action_queue_size_to_get_new_actions: int = 35
    task: str = field(default="make a foam ball skewer", metadata={"help": "Task to execute"})
    use_torch_compile: bool = False
    torch_compile_backend: str = "inductor"
    torch_compile_mode: str | None = None
    torch_compile_disable_cudagraphs: bool = True

    @classmethod
    def __get_path_fields__(cls) -> list[str]:
        return ["policy"]
