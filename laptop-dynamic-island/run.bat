@echo off
cd /d "%~dp0"
title Dynamic Island
echo Starting Dynamic Island...
echo Folder: %cd%
echo.

rem --- find a Python launcher (py or python) ---
set "PYEXE="
where py     >nul 2>nul && set "PYEXE=py"
if not defined PYEXE where python >nul 2>nul && set "PYEXE=python"

if not defined PYEXE (
  echo [X] Python was not found on this PC.
  echo     Install Python 3.10+ from https://python.org/downloads
  echo     and tick "Add python.exe to PATH".
  echo.
  pause
  goto :eof
)

echo Using %PYEXE% ...
%PYEXE% -m pip install -q -r requirements.txt
rem winrt powers the Spotify / media controls (has Python 3.14 wheels). Optional.
%PYEXE% -m pip install -q winrt-Windows.Media.Control 2>nul

%PYEXE% island.py
if errorlevel 1 pause
