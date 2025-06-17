# SQLAlchemy text() Auto-Fixer - PowerShell Script
# Save this as "fix_sqlalchemy.ps1" in your project root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SQLAlchemy text() Auto-Fixer" -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 Python found: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Python not found! Please install Python and add it to PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# First run in dry-run mode to preview changes
Write-Host "🔍 STEP 1: Previewing changes (DRY RUN)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
python fix_sqlalchemy_text.py . --dry-run

Write-Host ""

# Ask user if they want to proceed
$proceed = Read-Host "Do you want to apply these changes? (y/N)"
if ($proceed -ne "y" -and $proceed -ne "Y") {
    Write-Host "❌ Cancelled by user." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host ""
Write-Host "✅ STEP 2: Applying changes" -ForegroundColor Green
Write-Host "===========================" -ForegroundColor Green
python fix_sqlalchemy_text.py . --no-dry-run

Write-Host ""
Write-Host "🎉 Done! Check the output above for results." -ForegroundColor Green
Write-Host "💾 Original files have been backed up with .backup_* extension" -ForegroundColor Blue
Write-Host ""
Read-Host "Press Enter to exit"