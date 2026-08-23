@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch_word_search_creator.py"
) else (
    start "" pythonw "%~dp0launch_word_search_creator.py"
)
exit
