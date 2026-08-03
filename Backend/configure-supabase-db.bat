@echo off
setlocal
cd /d %~dp0

echo Trendbox Supabase PostgreSQL Config
echo.
set /p DB_HOST=DB_HOST: 
set /p DB_PORT=DB_PORT (kosongkan untuk 5432): 
if "%DB_PORT%"=="" set DB_PORT=5432
set /p DB_USER=DB_USER: 
set /p DB_PASSWORD=DB_PASSWORD: 
set /p DB_DATABASE=DB_DATABASE (kosongkan untuk postgres): 
if "%DB_DATABASE%"=="" set DB_DATABASE=postgres

(
echo DB_HOST=%DB_HOST%
echo DB_PORT=%DB_PORT%
echo DB_USER=%DB_USER%
echo DB_PASSWORD=%DB_PASSWORD%
echo DB_DATABASE=%DB_DATABASE%
echo DB_NAME=%DB_DATABASE%
echo FRONTEND_ORIGINS=*
) > .env

for %%D in (DMPKENV-main REPORTENV-main API-NLP-CHATBOT-QUERY-GENERATOR-main) do (
  copy /Y .env "%%D\.env" > nul
)

echo.
echo Konfigurasi Supabase berhasil disimpan ke Backend\.env dan disalin ke service Flask.
echo.
type .env
echo.
pause
