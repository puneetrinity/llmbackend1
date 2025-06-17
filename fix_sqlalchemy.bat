@echo off
REM SQLAlchemy text() Auto-Fixer - Windows Batch Script
REM Save this as "fix_sqlalchemy.bat" in your project root

echo.
echo ========================================
echo   SQLAlchemy text() Auto-Fixer
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python and add it to PATH.
    pause
    exit /b 1
)

echo 🐍 Python found!
echo.

REM First run in dry-run mode to preview changes
echo 🔍 STEP 1: Previewing changes (DRY RUN)
echo ==========================================
python fix_sqlalchemy_text.py . --dry-run
echo.

REM Ask user if they want to proceed
set /p proceed="Do you want to apply these changes? (y/N): "
if /i not "%proceed%"=="y" (
    echo ❌ Cancelled by user.
    pause
    exit /b 0
)

echo.
echo ✅ STEP 2: Applying changes
echo ===========================
python fix_sqlalchemy_text.py . --no-dry-run

echo.
echo 🎉 Done! Check the output above for results.
echo 💾 Original files have been backed up with .backup_* extension
echo.
pause