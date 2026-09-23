' Run this once (double-click it). Creates a "Bible Connections"
' shortcut on your Desktop, with a real icon, pointing at launch.vbs in
' this same folder -- that shortcut is what you double-click every time
' after this to actually open the app.
'
' A .vbs file can't carry its own custom icon in Windows Explorer (it
' always shows the default script icon); a shortcut TO one can, which
' is the only reason this two-step setup exists at all.
'
' Safe to run again later -- e.g. if you move or re-download the
' project folder -- it just rewrites the shortcut to point at the new
' location.
Dim shell, fso, scriptDir, desktopPath, shortcut, Q

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopPath = shell.SpecialFolders("Desktop")
Q = Chr(34)

Set shortcut = shell.CreateShortcut(desktopPath & "\Bible Connections.lnk")
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = Q & scriptDir & "\launch.vbs" & Q
shortcut.IconLocation = scriptDir & "\BibleConnections.ico"
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "Bible Connections"
shortcut.Save

MsgBox "A Bible Connections shortcut with its own icon was added to your " & _
       "Desktop." & vbCrLf & vbCrLf & "Double-click it any time to open the app.", _
       vbInformation, "Bible Connections"
