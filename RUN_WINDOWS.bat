@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo WindGrid - Streamlit 앱을 시작합니다.
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.11 이상을 먼저 설치해 주세요. 설치 시 Add Python to PATH를 선택하세요.
        pause
        exit /b 1
    )
    python -m venv .venv
)
if errorlevel 1 goto fail
:install
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m streamlit run app.py
pause
exit /b 0
:fail
echo 설치 또는 실행에 실패했습니다. 인터넷 연결 및 Python 버전을 확인해 주세요.
pause
exit /b 1
