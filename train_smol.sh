accelerate launch --multi-gpu $(which lerobot-train) \
--dataset.repo_id=Aasdfip/pretrain \
--dataset.video_backend=pyav \
--policy.path=HuggingFaceVLA/smolvla_libero \
--rename_map='{"observation.images.right_top":"observation.images.camera2","observation.images.left_wrist":"observation.images.camera1","observation.images.right_wrist":"observation.images.camera3"}' \
--policy.device=cuda \
--policy.train_expert_only=false \
--output_dir=outputs/train/smol_pretrain \
--batch_size=64 \
--steps=50000 \
--policy.freeze_vision_encoder=false \
--wandb.enable=true \
--policy.repo_id="Aasdfip/smolvla_pretrain_goldeen" \
--policy.optimizer_weight_decay=0.0000000001 \
--policy.optimizer_lr=0.0000175 \
--log_freq=30 \
--eval_freq=10000000 \
--save_freq=5000

