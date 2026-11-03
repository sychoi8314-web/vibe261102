@echo off
rem Build script for KOSPI200 Crawler (.exe)
rem Output: dist\Kospi200Crawler.exe
cd /d "%~dp0"

echo [1/2] Installing required packages...
python -m pip install --upgrade pyinstaller PyQt6 requests beautifulsoup4 openpyxl || goto :error

echo [2/2] Building executable...
rem --onefile  : bundle everything into a single exe
rem --windowed : no console window (GUI app)
rem --clean    : clear PyInstaller cache before building
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Kospi200Crawler ^
    kospi200_crawler.py || goto :error

echo.
echo Build complete: %~dp0dist\Kospi200Crawler.exe
exit /b 0

:error
echo Build failed.
exit /b 1
