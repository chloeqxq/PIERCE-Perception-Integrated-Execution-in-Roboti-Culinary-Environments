@echo off
setlocal enabledelayedexpansion
echo ===================================================
echo   LeRobot USB Auto-Attach Script for WSL (Windows)
echo ===================================================
echo.

:: Loop through usbipd list and automatically attach all Shared devices
echo Looking for Shared USB devices...
for /f "tokens=1,4" %%A in ('usbipd list ^| findstr "Shared"') do (
    echo Found Shared device on BUSID %%A. Attaching to WSL...
    usbipd attach --wsl --busid %%A
)

echo.
echo ===================================================
echo Done! All Shared cameras and robot arms should be inside WSL.
echo You can now go to your Cursor (WSL) terminal and run the code.
echo ===================================================
pause
