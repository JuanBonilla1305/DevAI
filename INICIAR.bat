@echo off
chcp 65001 > nul
title Retro 80s IA - NO CERRAR ESTA VENTANA
cd /d "%~dp0sanjuanero\sanjuanero-node"

echo ==========================================
echo    RETRO 80s IA
echo ==========================================
echo.

REM Motor FLUX.2 Klein sobre CUDA: el mismo modelo del proyecto original,
REM pero usando la tarjeta grafica. Unos 37 segundos de generacion en vez
REM de 318 que tardaba por CPU.
set MOTOR=flux2

REM Modo sin conexion. Los modelos ya estan descargados; sin esto Hugging
REM Face intenta comprobar si hay versiones nuevas y, con un wifi malo o
REM sin internet, la primera foto se queda esperando a que expire.
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

echo Arrancando el programa...
echo.
echo   - El navegador se abre solo en unos segundos.
echo   - NO CIERRES ESTA VENTANA: aqui es donde corre todo.
echo   - Para apagarlo, cierra esta ventana o pulsa Ctrl+C.
echo.

REM El navegador se abre con retraso: si se abre antes de que el servidor
REM este escuchando, el usuario ve un error de conexion y cree que fallo.
start "" cmd /c "timeout /t 10 > nul & start """" http://127.0.0.1:3000"

node server.js

echo.
echo ==========================================
echo  El programa se detuvo.
echo ==========================================
echo Si no fue a proposito, mira los mensajes de arriba.
echo Causa mas comun: el puerto 3000 ya estaba ocupado
echo por otra copia abierta.
echo.
pause
