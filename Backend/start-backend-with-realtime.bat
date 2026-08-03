@echo off
cd /d %~dp0
python run_backends.py --include-realtime
pause
