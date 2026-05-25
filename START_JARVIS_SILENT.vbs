'' START_JARVIS_SILENT.vbs
'' Double-click this to start JARVIS with no visible windows.
'' Logs go to: server_out.txt, server_err.txt, frontend_out.txt

Dim shell
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & _
    CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & _
    "\START_JARVIS.ps1""", 0, False
Set shell = Nothing
