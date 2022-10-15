@ECHO OFF
set "PYCMD=c:\python\python39\python.exe"

REM 
REM  Bootstrap script
REM 

set daemon=0
for %%f in (%*) do (
  if "%%f"=="-daemon" (
     set daemon=1
  )
)

if "%daemon%" == "1" (
  start %PYCMD%  %~p0\bootstrap.py %*
) else (
  %PYCMD%  %~p0\bootstrap.py %*
)