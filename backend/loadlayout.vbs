' Load a saved Logos layout by name through Logos's documented COM API (LoadLayout, API v3+).
' Usage, in the Logos Wine prefix: cscript //nologo loadlayout.vbs Layout name [:: John 3:16]
' With "::" and a reference, the layout's Bible (linked panels follow) goes to that passage.
' Prints "loaded" (plus a "passage: ..." line), "missing" or "error: ..."; exits 0, 3 or 1.
Option Explicit
Dim args, name, ref, launcher, app, i, inRef
Set args = WScript.Arguments
If args.Count < 1 Then
    WScript.Echo "error: no layout name"
    WScript.Quit 2
End If
' Ou Dedetai's --wine splits arguments on spaces, so join them back up
name = "" : ref = "" : inRef = False
For i = 0 To args.Count - 1
    If args(i) = "::" Then
        inRef = True
    ElseIf inRef Then
        ref = Trim(ref & " " & args(i))
    Else
        name = Trim(name & " " & args(i))
    End If
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
    If ref <> "" Then WScript.Echo "passage: " & GoToPassage(app, ref)
    WScript.Quit 0
End If
If Err.Number <> 0 Then
    WScript.Echo "error: " & Hex(Err.Number) & " " & Err.Description
    WScript.Quit 1
End If
WScript.Echo "missing"
WScript.Quit 3

' Send the layout's Bible to the passage: prefer a Resource panel in a link set (so linked
' guides and commentaries follow), else the most recently used Resource panel. Falls back to
' a logosref: link (your preferred Bible) if the panel can't be navigated.
Function GoToPassage(app, ref)
    Dim panels, panel, target, req, k
    On Error Resume Next
    WScript.Sleep 1500  ' let the layout finish opening
    Set target = Nothing
    Set panels = app.GetOpenPanels()
    For k = 0 To panels.Count - 1
        Set panel = panels.Item(k)
        If panel.Kind = "Resource" Then
            If target Is Nothing Then Set target = panel
            If panel.LinkSet <> "None" And panel.LinkSet <> "" Then
                Set target = panel
                Exit For
            End If
        End If
    Next
    Err.Clear
    If Not target Is Nothing Then
        Set req = app.CreateNavigationRequest()
        Set req.Reference = app.DataTypes.GetDataType("bible").ParseReference(ref)
        If Err.Number = 0 Then target.Navigate req
        If Err.Number = 0 Then
            GoToPassage = "navigated " & target.Title & " (" & target.LinkSet & ")"
            Exit Function
        End If
        GoToPassage = "panel navigation failed (" & Hex(Err.Number) & " " & Err.Description & "); "
        Err.Clear
    End If
    app.ExecuteUri "logosref:Bible." & Replace(ref, " ", "")
    If Err.Number = 0 Then
        GoToPassage = GoToPassage & "opened with logosref"
    Else
        GoToPassage = GoToPassage & "logosref failed (" & Hex(Err.Number) & ")"
    End If
End Function
