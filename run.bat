@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist venv (echo Сначала запустите setup.bat & pause & exit /b 1)
call venv\Scripts\activate.bat
start "" http://127.0.0.1:8000/
python manage.py runserver
