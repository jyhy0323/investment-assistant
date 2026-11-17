@echo off
chcp 65001 > nul
python "%~dp0analyze_stocks.py"
pause
