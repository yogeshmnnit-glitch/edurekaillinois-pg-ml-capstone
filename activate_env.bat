@echo off

:: Path to the .venv folder (relative to this bat file's location)
set "VENV_DIR=%~dp0.venv"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ERROR: .venv not found at %VENV_DIR%
    echo Run create_venv.bat first to create the environment.
    exit /b 1
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
echo Virtual environment activated.

