@echo off
echo Clearing Python cache...
cd /d "%~dp0"
if exist __pycache__ rmdir /s /q __pycache__
echo Cache cleared.
echo.
echo Starting Unified Intent Amplifier...
python main.py
pause
