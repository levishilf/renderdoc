@echo off
set RENDERDOC_PYTHON_PREFIX64=C:\Users\alvinshi\AppData\Local\Programs\Python\Python310
set MSBUILD="C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\MSBuild\Current\Bin\amd64\MSBuild.exe"
set COMMON=/p:Configuration=Release /p:Platform=x64 /p:PlatformToolset=v142 /p:WindowsTargetPlatformVersion=10.0.20348.0 /p:LibGit2SharpPath= /nodeReuse:false

echo === Building full solution (Release x64) ===
%MSBUILD% renderdoc.sln %COMMON%
echo ERRORLEVEL=%ERRORLEVEL%
