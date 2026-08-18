@echo off
rem ============================================================
rem  webvnc 启动脚本（图形控制台）
rem  使用项目内置的 Python 3.14 嵌入式运行环境，无需系统安装 Python
rem ============================================================

rem 切换控制台代码页为 UTF-8（65001），保证中文显示正常
chcp 65001 >nul

rem 强制 Python 全部使用 UTF-8 编码
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"

if not exist "python\python.exe" (
    echo [错误] 未找到内置运行环境 python\python.exe
    pause
    exit /b 1
)

rem 启动图形控制台：在界面中点击「启动服务」运行服务端
rem （服务端首次启动会自动检测并安装 Pillow，完成后自动重启）
"python\pythonw.exe" gui.py
if errorlevel 1 "python\python.exe" gui.py

rem 如需跳过图形界面直接运行服务端，可执行：
rem   python\python.exe webvnc.py
