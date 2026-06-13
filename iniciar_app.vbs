Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory
' Ensure we are running from the script directory
Set fso = CreateObject("Scripting.FileSystemObject")
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptDir

' Run the batch file hidden (0)
WshShell.Run chr(34) & strScriptDir & "\run_app.bat" & Chr(34), 0
Set WshShell = Nothing
