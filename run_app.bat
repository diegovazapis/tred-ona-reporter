@echo off
cd /d "%~dp0"

:: Check if venv exists
if not exist ".venv" (
    echo Virtual Environment not found. Creating one...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

:: Run Streamlit
streamlit run app.py --server.headless=false

:: If streamlit crashes, we want to know why (but in hidden mode we can't see)
:: For production, we don't pause.
