@ECHO OFF
set "PYCMD=python.exe"

REM 
REM  Bootstrap script
REM 

set daemon=0
for %%f in (%*) do (
  if "%%f"=="-daemon" (
     set daemon=1
  )
)

set site=%~p0\..\site-packages
set PYTHONPATH=%site%

if "%daemon%" == "1" (
  start %PYCMD%  %site%\bin\bayserver_py %*
) else (
  %PYCMD%  %site%\bin\bayserver_py %*
)