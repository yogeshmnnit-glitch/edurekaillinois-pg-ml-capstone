de@echo off
setlocal

:: Default target folder is current directory
set "TARGET_DIR=%CD%"

:: If a folder path is passed as argument, use it
if not "%~1"=="" (
    set "TARGET_DIR=%~1"
)

echo Creating .venv in: %TARGET_DIR%

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    exit /b 1
)

:: Check if .venv already exists
if exist "%TARGET_DIR%\.venv\" (
    echo .venv already exists in %TARGET_DIR%
    choice /C YN /M "Recreate it?"
    if errorlevel 2 goto :done
    echo Removing existing .venv...
    rmdir /s /q "%TARGET_DIR%\.venv"
)

:: Create the virtual environment
python -m venv "%TARGET_DIR%\.venv"
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
)

echo.
echo .venv created successfully at: %TARGET_DIR%\.venv
echo.
echo To activate, run:
echo     %TARGET_DIR%\.venv\Scripts\activate.bat

:done
endlocal
