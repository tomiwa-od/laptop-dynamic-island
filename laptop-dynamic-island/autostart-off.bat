@echo off
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('Startup')+'\DynamicIsland.lnk') -ErrorAction SilentlyContinue"
echo.
echo Removed the Dynamic Island from startup.
echo.
pause
