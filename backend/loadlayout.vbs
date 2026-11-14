' Load a saved Logos layout by name through Logos's documented COM API (LoadLayout, API v3+).
' Usage, in the Logos Wine prefix: cscript //nologo loadlayout.vbs Layout name
' Prints "loaded", "missing" or "error: ..." and exits 0, 3 or 1.
Option Explicit
Dim args, name, launcher, app, i
Set args = WScript.Arguments
If args.Count < 1 Then
    WScript.Echo "error: no layout name"
    WScript.Quit 2
End If
' Ou Dedetai's --wine splits arguments on spaces, so join them back into one name
name = args(0)
For i = 1 To args.Count - 1
    name = name & " " & args(i)
Next
On Error Resume Next
Set launcher = CreateObject("LogosBibleSoftware.Launcher")
If Err.Number <> 0 Then
    WScript.Echo "error: can't reach Logos's COM API (" & Hex(Err.Number) & "): " & Err.Description
    WScript.Quit 1
End If
Set app = launcher.Application
If app Is Nothing Then
    launcher.LaunchApplication
    For i = 1 To 120
        WScript.Sleep 1000
        Set app = launcher.Application
        If Not app Is Nothing Then Exit For
    Next
End If
If app Is Nothing Then
    WScript.Echo "error: Logos did not start"
    WScript.Quit 1
End If
If app.LoadLayout(name) Then
    WScript.Echo "loaded"
    WScript.Quit 0
End If
If Err.Number <> 0 Then
    WScript.Echo "error: " & Hex(Err.Number) & " " & Err.Description
    WScript.Quit 1
End If
WScript.Echo "missing"
WScript.Quit 3
