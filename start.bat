@echo off
chcp 65001 >nul
cd /d "%~dp0"
for /f "tokens=*" %%i in ('py -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set PYTHONW=%%i
start "" "%PYTHONW%" "%~dp0display_guard.py"
