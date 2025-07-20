@echo off
echo ===== Пересоздание виртуального окружения Python =====
echo.

cd /d C:\Docs\tbot\fin_track
echo Текущая директория: %CD%
echo.

echo Удаление старого venv (если существует)...
rmdir /s /q venv
echo.

echo Создание нового venv...
python -m venv venv
echo.

echo Активация нового venv...
call venv\Scripts\activate.bat
echo.

echo Установка зависимостей:
pip install python-telegram-bot==13.7 pandas openpyxl requests
echo.

echo Готово! Теперь запустите start_bot.bat
pause
