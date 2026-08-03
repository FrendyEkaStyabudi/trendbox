@echo off
cd /d %~dp0
npm run dev -- -H 0.0.0.0
pause
