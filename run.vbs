Set WinScriptHost = CreateObject("WScript.Shell")
' 0 hides the window, True waits for it to finish
WinScriptHost.Run "pythonw.exe ""C:\Starlight Manor Command\launcher.py""", 0, False
Set WinScriptHost = Nothing