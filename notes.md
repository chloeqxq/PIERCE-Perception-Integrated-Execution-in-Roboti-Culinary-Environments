lerobot-teleoperate --robot.id=nakbot --robot.type=so101_follower --robot.port=/dev/ttyACM0 --teleop.type=gamepad --robot.cameras="{ wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}"

lerobot-teleoperate --robot.id=nakbot --robot.type=so101_follower --robot.port=/dev/ttyACM0 --teleop.type=gamepad 

lerobot-teleoperate --robot.id=nakbot --robot.type=so101_follower --robot.port=/dev/ttyACM0 --teleop.type=gamepad 

lerobot-teleoperate --robot.id=qixinbot --robot.type=so101_follower --robot.port=/dev/ttyACM0 --teleop.type=so101_leader --teleop.id=so_leader --teleop.port=/dev/ttyACM1

lerobot-calibrate --teleop.type=so101_leader --teleop.port=/dev/ttyACM1 --teleop.id=so_leader

lerobot-calibrate --robot.id=nakbot --robot.type=so101_follower --robot.port=/dev/ttyACM0

lerobot-teleoperate --robot.id=nakbot --robot.type=so101_follower --robot.port=/dev/ttyACM0 --teleop.type=so101_leader --teleop.id=so_leader --teleop.port=/dev/ttyACM1

lerobot-teleoperate --robot.type=bi_so_follower --teleop.type=bi_so_leader --robot.id=bot --teleop.id=leader \
--robot.left_arm_config.port=/dev/ttyACM1 --robot.right_arm_config.port=/dev/ttyACM0 \
--teleop.left_arm_config.port=/dev/ttyACM3 --teleop.right_arm_config.port=/dev/ttyACM2 \





lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=nakbot \
  --robot.cameras="{ camera1: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --display_data=true \
  --dataset.repo_id=Aasdfip/eval_test_vla_72 \
  --dataset.num_episodes=10 \
  --dataset.single_task="pick up orange peel" \
  --policy.path=lerobot/smolvla_base


lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=nakbot \
  --robot.cameras="{ gripper: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --display_data=true \
  --dataset.repo_id=Aasdfip/eval_test_act_n \
  --dataset.num_episodes=1 \
  --dataset.single_task="pick up the bottle" \
  --policy.type=act


  lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=nakbot \
  --robot.cameras="{ camera1: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, backend: }}" \
  --display_data=true \
  --dataset.repo_id=Aasdfip/eval_test_vla_7 \
  --dataset.num_episodes=10 \
  --dataset.single_task="pick up the bottle" \
  --policy.path=lerobot/smolvla_base