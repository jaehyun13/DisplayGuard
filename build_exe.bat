@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/3] 의존성 설치 중...
py -m pip install pyinstaller pystray Pillow --quiet

echo [2/3] 아이콘 생성 중...
py -c "from create_shortcut import create_ico; create_ico('icon.ico')"

echo [3/3] 빌드 중 (잠시 걸립니다)...
py -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name DisplayGuard ^
    --icon icon.ico ^
    --collect-submodules pystray ^
    --collect-submodules PIL ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    display_guard.py

echo.
if exist dist\DisplayGuard.exe (
    echo 빌드 성공! dist\DisplayGuard.exe
    copy /y dist\DisplayGuard.exe DisplayGuard.exe
    echo 현재 폴더에 DisplayGuard.exe 복사 완료
) else (
    echo 빌드 실패. 위 오류 메시지를 확인하세요.
)
pause
