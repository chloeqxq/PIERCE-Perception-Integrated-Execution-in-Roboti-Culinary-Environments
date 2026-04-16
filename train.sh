lerobot-train \
--dataset.repo_id=Aasdfip/pretrain \
--dataset.video_backend=pyav \
--policy.path=lerobot/smolvla_base \
--rename_map='{"observation.images.right_top":"observation.images.camera1","observation.images.left_wrist":"observation.images.camera2","observation.images.right_wrist":"observation.images.camera3"}' \
--policy.device=cuda \
--policy.train_expert_only=false \
--output_dir=outputs/train/smol_pretrain \
--batch_size=16 \
--steps=5000000 \
--policy.freeze_vision_encoder=true \
--wandb.enable=true \
--policy.repo_id="Aasdfip/smolvla_pretrain" \
--policy.optimizer_weight_decay=0.0000000001 \
--policy.optimizer_lr=0.0000175 \
--log_freq=30 \
--eval_freq=10000000 \
--save_freq=4000

