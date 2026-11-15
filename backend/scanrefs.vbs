' Find Bible references in text with Logos's own parser (DataTypes "bible": ParseReference,
' then ScanForReferences; COM API v2+). Only if Logos is already running: it never starts Logos.
' Reads scanrefs-in.txt (UTF-16) next to this script and writes scanrefs-out.txt (UTF-16), one
' reference per line as "<saved form><TAB><display form>", e.g. "Bible.Jn1.10<TAB>John 1:10".
' Prints "found N", "notrunning" or "error: ...".
Option Explicit
Dim fso, here, f, text, launcher, app, bible, r, found, item, out, n
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
On Error Resume Next
Set f = fso.OpenTextFile(fso.BuildPath(here, "scanrefs-in.txt"), 1, False, -1)   ' read, Unicode
text = f.ReadAll
f.Close
If Err.Number <> 0 Then
    WScript.Echo "error: couldn't read scanrefs-in.txt (" & Hex(Err.Number) & ")"
    WScript.Quit 1
End If
Set launcher = CreateObject("LogosBibleSoftware.Launcher")
If Err.Number <> 0 Then
    WScript.Echo "error: can't reach Logos's COM API (" & Hex(Err.Number) & "): " & Err.Description
    WScript.Quit 1
End If
Set app = launcher.Application
If app Is Nothing Then
    WScript.Echo "notrunning"
    WScript.Quit 4
End If
Set bible = app.DataTypes.GetDataType("bible")
Set out = fso.CreateTextFile(fso.BuildPath(here, "scanrefs-out.txt"), True, True)  ' overwrite, Unicode
n = 0
' A short selection is most likely a single reference however it's written ("jn 1v10")
If Len(Trim(text)) <= 40 Then
    Set r = Nothing
    Set r = bible.ParseReference(Trim(text))
    If Err.Number = 0 And Not r Is Nothing Then
        out.WriteLine r.Save() & vbTab & r.Render()
        n = 1
    End If
    Err.Clear
End If
If n = 0 Then
    Set found = bible.ScanForReferences(text)
    If Err.Number = 0 And Not found Is Nothing Then
        For Each item In found
            out.WriteLine item.Reference.Save() & vbTab & item.Reference.Render()
            n = n + 1
        Next
    End If
    Err.Clear
End If
out.Close
WScript.Echo "found " & n
