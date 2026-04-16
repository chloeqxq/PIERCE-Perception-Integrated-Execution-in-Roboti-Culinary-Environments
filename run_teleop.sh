#!/bin/bash

echo "=================================================="
echo "    LeRobot Teleoperation Script (WSL Linux)      "
echo "=================================================="

# Check if devices are mounted
echo "Checking if USB devices are attached from Windows..."
count_tty=$(ls -1 /dev/ttyACM* 2>/dev/null | wc -l)
count_video=$(ls -1 /dev/video* 2>/dev/null | wc -l)

if [ "$count_tty" -eq 0 ] && [ "$count_video" -eq 0 ]; then
    echo "⚠️ Warning: No robot arms or cameras found!"
    echo "Did you run 'attach_usb.bat' as Administrator on Windows?"
    exit 1
fi

echo "Found $count_tty serial arms and $count_video video streams."

# Request password for chmod 666
echo ""
echo "Please enter your WSL password to grant read/write permissions to the robot hardware:"
sudo chmod 666 /dev/ttyACM* /dev/video*

echo "Permissions granted! Starting the robot..."
echo "=================================================="

# Run the python script
python teleop.py
