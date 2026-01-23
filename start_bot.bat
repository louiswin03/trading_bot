@echo off
title Trading Bot - ADX Strategy 24/7
color 0A

echo ========================================
echo   TRADING BOT - STARTING
echo ========================================
echo.

cd /d "%~dp0"

:loop
echo [%date% %time%] Starting bot with position tracking...
python bot_with_position_tracking.py

echo.
echo [%date% %time%] Bot stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak
goto loop
