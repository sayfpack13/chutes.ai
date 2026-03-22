@echo off
cd /d "%~dp0"
python -m uvicorn dashboard.main:app --reload --port 8765 --reload-dir dashboard --reload-dir core
