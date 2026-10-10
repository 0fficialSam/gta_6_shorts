@echo off
echo ========================================
echo    GTA 6 Shorts Automation Starting...
echo ========================================
cd /d "%~dp0"
python main.py >> logs\daily.log 2>&1
echo Done! Check output\ folder for your video.
pause
