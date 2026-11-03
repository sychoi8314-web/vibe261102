@echo off
rem Build script for Naver News Crawler (.exe)
rem Output: dist\NaverNewsCrawler.exe
cd /d "%~dp0"

echo [1/2] Installing required packages...
python -m pip install --upgrade pyinstaller PyQt6 requests beautifulsoup4 openpyxl || goto :error

echo [2/2] Building executable...
rem --onefile  : bundle everything into a single exe
rem --windowed : no console window (GUI app)
rem --clean    : clear PyInstaller cache before building
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name NaverNewsCrawler ^
    naver_news_crawler.py || goto :error

echo.
echo Build complete: %~dp0dist\NaverNewsCrawler.exe
exit /b 0

:error
echo Build failed.
exit /b 1
