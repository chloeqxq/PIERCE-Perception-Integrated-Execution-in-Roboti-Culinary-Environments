from __future__ import annotations

import copy
import logging
from dataclasses import dataclass

import torch

from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies import PI0Config, PI05Config, SmolVLAConfig
from lerobot.policies.factory import get_policy_class
from lerobot.processor.factory import (
    make_default_robot_action_processor,
    make_default_robot_observation_processor,
)

logger = logging.getLogger(__name__)


POLICY_CONFIG_TYPES = {
    "smolvla": SmolVLAConfig,
    "pi05": PI05Config,
    "pi0": PI0Config,
}


@dataclass
class PolicyBundle:
    policy: object
    policy_cfg: object
    robot_observation_processor: object
    robot_action_processor: object
    pretrained_path: str
    policy_type: str


def _clone_policy_cfg(policy_cfg, pretrained_path: str | None = None, policy_type: str | None = None):
    requested_type = policy_type or getattr(policy_cfg, "type", None)

    if policy_type and requested_type != getattr(policy_cfg, "type", None):
        config_cls = POLICY_CONFIG_TYPES.get(requested_type)
        if config_cls is None:
            raise ValueError(f"Unsupported policy_type '{requested_type}'")
        return config_cls(pretrained_path=pretrained_path or policy_cfg.pretrained_path)

    cloned = copy.deepcopy(policy_cfg)
    if pretrained_path is not None:
        cloned.pretrained_path = pretrained_path
    return cloned


def _apply_torch_compile(policy, cfg):
    if policy.type in {"pi05", "pi0"}:
        return policy

    try:
        if not hasattr(torch, "compile"):
            logger.warning(
                "torch.compile is not available. Requires PyTorch 2.0+. Current version: %s.",
                torch.__version__,
            )
            return policy

        compile_kwargs = {
            "backend": cfg.torch_compile_backend,
            "mode": cfg.torch_compile_mode,
        }
        if cfg.torch_compile_disable_cudagraphs:
            compile_kwargs["options"] = {"triton.cudagraphs": False}

        policy.predict_action_chunk = torch.compile(policy.predict_action_chunk, **compile_kwargs)
        logger.info("Successfully compiled predict_action_chunk")
    except Exception as exc:
        logger.error("Failed to apply torch.compile: %s", exc)
        logger.warning("Continuing without torch.compile")

    return policy


def load_policy_bundle(cfg, *, pretrained_path: str | None = None, policy_type: str | None = None) -> PolicyBundle:
    policy_cfg = _clone_policy_cfg(cfg.policy, pretrained_path=pretrained_path, policy_type=policy_type)
    policy_class = get_policy_class(policy_cfg.type)

    config = PreTrainedConfig.from_pretrained(policy_cfg.pretrained_path)
    if policy_cfg.type in {"pi05", "pi0"}:
        config.compile_model = cfg.use_torch_compile

    if config.use_peft:
        from peft import PeftConfig, PeftModel

        peft_pretrained_path = policy_cfg.pretrained_path
        peft_config = PeftConfig.from_pretrained(peft_pretrained_path)
        policy = policy_class.from_pretrained(
            pretrained_name_or_path=peft_config.base_model_name_or_path,
            config=config,
        )
        policy = PeftModel.from_pretrained(policy, peft_pretrained_path, config=peft_config)
    else:
        policy = policy_class.from_pretrained(policy_cfg.pretrained_path, config=config)

    policy.config.rtc_config = cfg.rtc
    policy.init_rtc_processor()
    assert policy.name in ["smolvla", "pi05", "pi0"], "Only smolvla, pi05, and pi0 are supported for RTC"

    policy = policy.to(cfg.device)
    policy.eval()

    if cfg.use_torch_compile:
        policy = _apply_torch_compile(policy, cfg)

    return PolicyBundle(
        policy=policy,
        policy_cfg=policy_cfg,
        robot_observation_processor=make_default_robot_observation_processor(),
        robot_action_processor=make_default_robot_action_processor(),
        pretrained_path=policy_cfg.pretrained_path,
        policy_type=policy_cfg.type,
    )