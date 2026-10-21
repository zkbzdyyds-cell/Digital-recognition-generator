@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title IMAGE OBSERVER - BUILD 02.3
pushd "%~dp0"
if errorlevel 1 goto bad_folder
set "PYTHONUTF8=1"
set "GRADIO_ANALYTICS_ENABLED=False"
set "PY_CHECK=import sys,struct;sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)"
for %%F in ("launcher.py" "app.py" "processor.py" "requirements.txt" "先读我.txt") do if not exist "%%~F" goto incomplete
if not exist ".venv\Scripts\python.exe" goto try_py
".venv\Scripts\python.exe" -c "%PY_CHECK%" >nul 2>&1
if not errorlevel 1 goto run_venv
:try_py
py -3.12 -c "%PY_CHECK%" >nul 2>&1
if not errorlevel 1 goto run_py
for /f "delims=" %%P in ('where python 2^>nul ^| findstr /I /L /V /C:"WindowsApps"') do (
  "%%P" -c "%PY_CHECK%" >nul 2>&1
  if not errorlevel 1 (
    set "FALLBACK_PYTHON=%%P"
    goto run_python
  )
)
goto no_python
:run_venv
".venv\Scripts\python.exe" launcher.py
set "START_EXIT=%errorlevel%"
goto finished
:run_py
py -3.12 launcher.py
set "START_EXIT=%errorlevel%"
goto finished
:run_python
"%FALLBACK_PYTHON%" launcher.py
set "START_EXIT=%errorlevel%"
goto finished
:no_python
echo.
echo [需要安装 Python] 未找到 Python 3.12 64-bit。
echo 请先按自动打开的“先读我.txt”完成首次安装，然后重新双击本文件。
echo 官方下载：https://www.python.org/downloads/windows/
start "" notepad.exe "先读我.txt"
set "START_EXIT=1"
goto finished
:incomplete
echo.
echo [请先完整解压] 请右键 ZIP，选择“全部解压”，再双击启动工具.bat。
echo 不要在压缩包预览窗口内直接双击运行，也不要只复制 BAT 文件。
set "START_EXIT=1"
goto finished
:bad_folder
echo [无法打开项目文件夹] 请先把完整项目解压到桌面等可写的本地位置。
set "START_EXIT=1"
goto pause_only
:finished
echo.
if not "%START_EXIT%"=="0" echo [未能启动] 请阅读上方提示；详细信息见 launcher.log 或 install.log。
if "%START_EXIT%"=="0" echo IMAGE OBSERVER BUILD 02.3 已退出。
popd
:pause_only
echo 按任意键关闭此窗口。
pause >nul
exit /b %START_EXIT%
