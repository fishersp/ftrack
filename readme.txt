в боте используются библиотеки, которые работают только на версии 3.11
на компе установлена 3.13 для других целей
поэтому запускаем через venv:
bat файл с текстом
@echo off
cd /d C:\Docs\tbot\fin_track
call venv\Scripts\activate.bat
python telegram_fin_tracker.py
pause



Как создать окружение venv:
✅ 1. Создай виртуальное окружение под нужной версией Python
Если у тебя установлена нужная версия Python, например python3.10, то создай окружение:

bash
Копировать
Редактировать
python3.10 -m venv venv

✅ 2. Активируй виртуальное окружение
Windows (cmd):

cmd
Копировать
Редактировать
venv\Scripts\activate
Windows (PowerShell):

powershell
Копировать
Редактировать
.\venv\Scripts\Activate.ps1
Linux / macOS:

bash
Копировать
Редактировать
source venv/bin/activate
✅ 3. Установи зависимости
Внутри активированного окружения:

bash
Копировать
Редактировать
pip install -r requirements.txt
Если файла requirements.txt нет — установи вручную:

bash
Копировать
Редактировать
pip install python-telegram-bot pandas openpyxl
✅ 4. Запусти бота
bash
Копировать
Редактировать
python telegram_fin_tracker.py

✅ 5. Проверка, в какой версии Python ты работаешь
bash
Копировать
Редактировать
python --version


---------------------
Запуск кода версией python которая прописана в системе, пример:

python c:\\Docs\\tbot\\fin_track\\fetch_sheet_from_drive.py
