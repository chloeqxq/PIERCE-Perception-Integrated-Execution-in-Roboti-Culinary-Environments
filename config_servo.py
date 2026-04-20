from hardware import get_platform_ports
from lerobot.motors import feetech,Motor,MotorNormMode,MotorCalibration
ports = get_platform_ports()

port = ports['follower_right']

bus = feetech.FeetechMotorsBus(
    port = port,
    motors = {"base":Motor(id=7,norm_mode=MotorNormMode.DEGREES,model="sts3215")},
    calibration={"base":MotorCalibration(7,3,0,0,1)}
)

# bus.setup_motor("base_rotate")