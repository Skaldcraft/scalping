@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
python daily_run.py %*
