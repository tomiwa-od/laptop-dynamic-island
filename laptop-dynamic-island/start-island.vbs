' Launches the Dynamic Island with NO console window, detached from this process.
' Double-click this instead of run.bat for everyday use.
' (Run run.bat once first so the dependencies are installed.)

Set fso = CreateObject("Scripting.FileSystemObject")
d = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = d
' Try pythonw (windowless) first, then the launcher's windowless variant pyw.
sh.Run "cmd /c pythonw island.py 2>nul || pyw island.py", 0, False
