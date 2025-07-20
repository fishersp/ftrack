@echo off
chcp 65001 > nul
echo ===== Запуск финансового бота =====
echo.

cd /d C:\Docs\tbot\fin_track
echo Текущая директория: %CD%
echo.

echo Активация виртуального окружения...
call venv\Scripts\activate.bat || echo ОШИБКА: Не удалось активировать venv!
echo.

echo Проверка версии Python:
python --version
echo.

echo Установка/обновление зависимостей:
pip install python-telegram-bot==13.7 pandas openpyxl requests
echo.

echo Запуск бота:
python telegram_fin_tracker_latest.py
echo.

echo Бот остановлен.
pause
