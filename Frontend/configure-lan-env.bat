@echo off
setlocal
cd /d %~dp0

echo Trendbox Frontend LAN Config
echo.
set /p BACKEND_IP=Masukkan IP laptop backend/frontend (contoh 192.168.1.20, kosongkan untuk 127.0.0.1): 
if "%BACKEND_IP%"=="" set BACKEND_IP=127.0.0.1
set /p DETECTION_IP=Masukkan IP laptop detection/GPU (contoh 192.168.1.30, kosongkan untuk 127.0.0.1): 
if "%DETECTION_IP%"=="" set DETECTION_IP=127.0.0.1

(
echo NEXT_PUBLIC_API_BASE_URL=http://%BACKEND_IP%:5000
echo NEXT_PUBLIC_REPORT_API_BASE_URL=http://%BACKEND_IP%:5002
echo NEXT_PUBLIC_NLP_API_BASE_URL=http://%BACKEND_IP%:5003
echo NEXT_PUBLIC_REALTIME_API_URL=http://%DETECTION_IP%:5001
) > .env.local

echo.
echo .env.local berhasil dibuat:
type .env.local
echo.
echo Jalankan frontend dengan: npm run dev:lan
pause
