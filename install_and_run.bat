@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [DisplayGuard] 의존성 설치 중...
py -m pip install pystray Pillow
echo.
echo [DisplayGuard] 프로그램 실행 중...
for /f "tokens=*" %%i in ('py -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set PYTHONW=%%i
start "" "%PYTHONW%" "%~dp0display_guard.py"
echo 시스템 트레이(우측 하단 알림 영역)에서 초록색 아이콘을 확인하세요.
timeout /t 3
