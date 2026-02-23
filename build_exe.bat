@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "Counterfeit Clicker" --icon counterfeit_clicker.ico click.py
if %errorlevel% neq 0 (
  echo.
  echo Build failed.
  pause
  exit /b %errorlevel%
)
echo.
echo Build complete: dist\Counterfeit Clicker.exe
pause
