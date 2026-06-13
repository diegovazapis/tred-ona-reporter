# Check if python is in path
$pythonVersion = python --version 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Python not found. Initiating installation..." -ForegroundColor Yellow
    
    # Check winget
    $wingetVersion = winget --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Installing Python 3.11 via Winget..." -ForegroundColor Cyan
        winget install -e --id Python.Python.3.11 --scope machine
        
        if ($LASTEXITCODE -ne 0) {
             Write-Host "Winget installation failed. Opening download page..." -ForegroundColor Red
             Start-Process "https://www.python.org/downloads/"
             Read-Host "Press Enter after you have installed Python manually..."
        }
        
        # Refresh env vars for current session (basic attempt)
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
    else {
        Write-Host "Winget not found. Opening Python download page..." -ForegroundColor Yellow
        Start-Process "https://www.python.org/downloads/"
        Read-Host "Press Enter after you have installed Python manually..."
    }
} else {
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
}

# Verify again
$pythonCheck = python --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Critical: Python still not found. Exiting." -ForegroundColor Red
    Pause
    exit
}

# Setup Venv
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Activate and Install
Write-Host "Activating venv and checking dependencies..."
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run
Write-Host "Launching App..." -ForegroundColor Green
streamlit run app.py
