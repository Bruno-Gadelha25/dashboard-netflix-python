@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
set "PORT=8501"
netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if not errorlevel 1 set "PORT=8502"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -m streamlit run app.py --server.port %PORT%
) else (
    py -3.13 -m streamlit run app.py --server.port %PORT%
)

pause
