@echo off
title Sanjuanero IA - Node.js
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js no esta instalado.
  pause
  exit /b 1
)
if not exist node_modules (
  echo Instalando dependencias NPM...
  call npm install
  if errorlevel 1 (
    echo ERROR instalando NPM.
    pause
    exit /b 1
  )
)
echo.
echo SANJUANERO IA
 echo.
echo Abre: http://127.0.0.1:3000
echo.
call npm start
pause
