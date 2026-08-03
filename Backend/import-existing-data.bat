@echo off
cd /d %~dp0
python import-existing-data.py %*
