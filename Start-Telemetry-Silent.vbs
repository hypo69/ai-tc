' =============================================================================
' ai-tc Silent Telemetry Launcher (USB)
' Starts apps\windows\telemetry\main.py via runtime\python\pythonw.exe
' completely headless (no PowerShell or console window).
' Databases and logs remain in standard OS paths (%ProgramData%, %APPDATA%).
' =============================================================================
Option Explicit

Dim fso, shell, scriptDir, appDir, runtimeDir, pywExe, tlmScript
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
If fso.FileExists(fso.BuildPath(scriptDir, "apps\windows\telemetry\main.py")) Then
    appDir = scriptDir
Else
    appDir = fso.BuildPath(scriptDir, "ai-tc")
End If

runtimeDir = fso.BuildPath(appDir, "runtime")
pywExe     = fso.BuildPath(runtimeDir, "python\pythonw.exe")
tlmScript  = fso.BuildPath(appDir, "apps\windows\telemetry\main.py")

If Not fso.FileExists(pywExe) Then WScript.Quit 1
If Not fso.FileExists(tlmScript) Then WScript.Quit 1

' Prevent duplicate telemetry process
Dim wmi, procs, proc, cmdLine
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name LIKE 'python%.exe'")
For Each proc In procs
    cmdLine = ""
    On Error Resume Next
    cmdLine = LCase(CStr(proc.CommandLine))
    On Error GoTo 0
    If InStr(cmdLine, "windows\telemetry\main.py") > 0 Or InStr(cmdLine, "windows/telemetry/main.py") > 0 Then
        WScript.Quit 0
    End If
Next

' Configure process-local runtime environment (OS %APPDATA% / %ProgramData% untouched)
Dim env, progData
Set env = shell.Environment("PROCESS")
progData = env("ProgramData")
If progData = "" Then progData = "C:\ProgramData"
env("PYTHONUTF8") = "1"
env("PYTHONIOENCODING") = "utf-8"
env("PYTHONDONTWRITEBYTECODE") = "1"
env("PYTHONNOUSERSITE") = "1"
env("AITC_DIR") = appDir
env("AITC_RUNTIME_DIR") = runtimeDir
env("AITC_LOGS_DIR") = progData & "\ai-tc\logs"
env("AI_TC_LOGS_DIR") = progData & "\ai-tc\logs"
env("PATH") = runtimeDir & "\python;" & runtimeDir & "\python\Scripts;" & runtimeDir & "\bin;" & env("PATH")

shell.CurrentDirectory = appDir
' WindowStyle = 0 (SW_HIDE), WaitOnReturn = False -> completely silent start
shell.Run """" & pywExe & """ """ & tlmScript & """ --mode hybrid", 0, False
