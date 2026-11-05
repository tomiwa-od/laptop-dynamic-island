@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\DynamicIsland.lnk'); $s.TargetPath='%cd%\start-island.vbs'; $s.WorkingDirectory='%cd%'; $s.Save()"
echo.
echo Done. The Dynamic Island will now start silently every time you log in.
echo To undo, run autostart-off.bat.
echo.
pause
