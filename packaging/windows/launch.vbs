' Bible Connection launcher (Windows).
'
' Runs with no visible console window -- unlike a plain .bat double-
' click, which always flashes a black Command Prompt window -- and
' shows a native message box instead of printed text if the required
' Python packages aren't installed yet.
'
' Uses the "py" launcher (py -3) rather than plain "python"/"python3":
' py.exe is installed system-wide by the official python.org installer
' specifically to avoid PATH ambiguity, and is the standard way to find
' a real Python interpreter reliably on Windows. If "py" isn't present
' at all (e.g. Python installed some other way), the check below just
' fails like packages were missing -- same fix either way: open a real
' Command Prompt and follow the README, which would surface that too.
Dim shell, fso, scriptDir, projectDir, desktopDir, Q, checkCmd, exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)
desktopDir = projectDir & "\desktop"
Q = Chr(34)

checkCmd = "cmd /c cd /d " & Q & desktopDir & Q & " && py -3 -c " & Q & _
    "import fastapi, PySide6, sentence_transformers, bs4" & Q
exitCode = shell.Run(checkCmd, 0, True)

If exitCode <> 0 Then
    MsgBox "Required Python packages are not installed yet." & vbCrLf & vbCrLf & _
           "A Command Prompt window will open in this folder -- follow the " & _
           "Install the packages section in README.md there, then try opening " & _
           "this app again.", vbExclamation, "Bible Connection"
    shell.Run "cmd.exe /k cd /d " & Q & projectDir & Q, 1, False
    WScript.Quit 1
End If

shell.Run "cmd /c cd /d " & Q & desktopDir & Q & " && py -3 main.py", 0, False
