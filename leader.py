from lerobot.teleoperators import so_leader
PORT='/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6080418-if00'
config = so_leader.SO101LeaderConfig(port=PORT,id='leader_left')
leader = so_leader.SO101Leader(config)
leader.connect()