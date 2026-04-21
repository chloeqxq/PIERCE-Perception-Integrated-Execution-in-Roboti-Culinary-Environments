from hardware import get_platform_ports
from lerobot.motors import feetech,Motor,MotorNormMode,MotorCalibration
from lerobot.robots.so_follower import SO101Follower,SO101FollowerConfig
from pathlib import Path
ports = get_platform_ports()

port = ports['follower_right']

# bus = feetech.FeetechMotorsBus(
#     port = port,
#     motors = {"base":Motor(id=7,norm_mode=MotorNormMode.DEGREES,model="sts3215")},
#     calibration={"base":MotorCalibration(7,3,0,85,4095)}
# )


# bus.write("Operating_Mode","base",3)
# bus.write("Min_Position_Limit","base",0)
# bus.write("Max_Position_Limit","base",0)
# bus.write("Goal_Velocity","base",500)
# bus.write("Goal_Position",10)
# bus.setup_motor("base_rotate")

config = SO101FollowerConfig(port=port,id='bot_right',calibration_dir = Path('calibration/robots/so_follower'))
arm = SO101Follower(config)
arm.connect()
# arm.bus.write("Operating_Mode",None,3,motor_id=7,normalize=False)
# arm.bus.write("Min_Position_Limit",None,0,motor_id=7,normalize=False)
# arm.bus.write("Max_Position_Limit",None,0,motor_id=7,normalize=False)
# arm.bus.write("Goal_Velocity",None,500,motor_id=7,normalize=False)

# arm.bus.write("Goal_Position",None,50,motor_id=7,normalize=False)
