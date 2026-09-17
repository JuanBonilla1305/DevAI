@echo off
setlocal
cd /d "%~dp0"
echo Iniciando Sanjuanero IA...

set "PYTHON_COMMAND=python"

call python --version > nul 2>&1
if %errorlevel% equ 0 (
    echo Python command check :OK
) else (
    echo Error: Python no encontrado. Instala Python 3.10 o 3.11 e intenta de nuevo.
    pause
    exit /b 1
)

set PATH=%PATH%;%~dp0env\Lib\site-packages\openvino\libs
call "%~dp0env\Scripts\activate.bat" && %PYTHON_COMMAND% "%~dp0sanjuanero\app.py"

pause
