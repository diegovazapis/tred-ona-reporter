If ($?) {
    # Check if streamlit is running on port 8501
    $port = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
    
    if (-not $port) {
        Write-Host "Streamlit no detectado. Reiniciando..."
        Set-Location "C:\Generacion_documental\ona_reporter"
        # Run in background via Start-Process
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c .\venv\Scripts\activate && streamlit run app.py --server.headless=true" -WindowStyle Hidden
    } else {
        Write-Host "Streamlit está corriendo."
    }
}
