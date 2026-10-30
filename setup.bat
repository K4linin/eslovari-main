@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Установка eSlovari ===
python --version || (echo Python не найден. Установите Python 3.11+ с python.org и галочкой "Add Python to PATH". & pause & exit /b 1)
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || (echo Ошибка установки зависимостей. & pause & exit /b 1)
python deploy\make_env.py
python manage.py migrate || (pause & exit /b 1)
python manage.py seed_data
echo.
echo Придумайте логин и пароль администратора (пароль от 10 символов, буквы и цифры):
python manage.py createsuperuser
echo.
echo Готово! Запустите run.bat
pause
