' Copy Bible verses as text through Logos's documented COM API (CopyBibleVerses.GetText, API v2+):
' your preferred Bible, in the style last chosen in Logos's Copy Bible Verses tool.
' Usage, in the Logos Wine prefix: cscript //nologo copyverses.vbs John 3:16-18
' Writes the text (UTF-16) to copyverses.txt next to this script; prints "copied" or "error: ...".
Option Explicit
Dim args, ref, i, launcher, app, req, text, fso, outPath, f
Set args = WScript.Arguments
ref = ""
For i = 0 To args.Count - 1   ' Ou Dedetai's --wine splits arguments on spaces
    ref = Trim(ref & " " & args(i))
Next
If ref = "" Then
    WScript.Echo "error: no reference"
    WScript.Quit 2
End If
On Error Resume Next
Set launcher = CreateObject("LogosBibleSoftware.Launcher")
If Err.Number <> 0 Then
    WScript.Echo "error: can't reach Logos's COM API (" & Hex(Err.Number) & "): " & Err.Description
    WScript.Quit 1
End If
Set app = launcher.Application
If app Is Nothing Then
    WScript.Echo "error: Logos isn't running"
    WScript.Quit 1
End If
Set req = app.CopyBibleVerses.CreateRequest()
Set req.Reference = app.DataTypes.GetDataType("bible").ParseReference(ref)
If Err.Number <> 0 Or req.Reference Is Nothing Then
    WScript.Echo "error: Logos didn't recognise the reference """ & ref & """"
    WScript.Quit 1
End If
' Pass the request ByVal (extra parentheses): under Wine, passing an object ByRef across
' processes fails with error 5 "Invalid procedure call or argument".
text = app.CopyBibleVerses.GetText((req))
If Err.Number <> 0 Then
    WScript.Echo "error: " & Hex(Err.Number) & " " & Err.Description
    WScript.Quit 1
End If
Set fso = CreateObject("Scripting.FileSystemObject")
outPath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "copyverses.txt")
Set f = fso.CreateTextFile(outPath, True, True)   ' overwrite, Unicode
f.Write text
f.Close
If Err.Number <> 0 Then
    WScript.Echo "error: couldn't write " & outPath & " (" & Hex(Err.Number) & ")"
    WScript.Quit 1
End If
WScript.Echo "copied"
