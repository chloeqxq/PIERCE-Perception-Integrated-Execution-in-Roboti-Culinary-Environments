accelerate launch --multi-gpu $(which lerobot-train) \
--dataset.repo_id=Aasdfip/pretrain \
--dataset.video_backend=pyav \
--policy.path=/Projects/PIERCE-Perception-Integrated-Execution-in-Roboti-Culinary-Environments/outputs/train/pi05_pretrain/checkpoints/last/pretrained_model \
--rename_map='{"observation.images.right_top":"observation.images.base_0_rgb","observation.images.left_wrist":"observation.images.left_wrist_0_rgb","observation.images.right_wrist":"observation.images.right_wrist_0_rgb"}' \
--policy.device=cuda \
--policy.dtype=bfloat16 \
--policy.gradient_checkpointing=false \
--policy.train_expert_only=false \
--policy.push_to_hub=true \
--output_dir=outputs/train/pi05_pretrain_resume \
--batch_size=8 \
--steps=100000 \
--policy.freeze_vision_encoder=true \
--wandb.enable=true \
--policy.repo_id="Aasdfip/goldeen_pretrain_resume" \
--policy.optimizer_weight_decay=0.000000001 \
--policy.optimizer_lr=0.00002 \
--log_freq=30 \
--eval_freq=100000000 \
--save_freq=2000 \
--policy.normalization_mapping='{"ACTION": "MIN_MAX", "STATE": "MIN_MAX", "VISUAL": "IDENTITY"}'

#/Projects/PIERCE-Perception-Integrated-Execution-in-Roboti-Culinary-Environments/outputs/train/pi05_pretrain/checkpoints/last/pretrained_model

