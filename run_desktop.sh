#!/bin/bash
# webvnc Linux 虚拟桌面启动脚本
# 启动 Xvfb 虚拟屏幕 + openbox 窗口管理器 + 基础应用，
# 让 webvnc 抓取真实 X 桌面（而非演示画面）。
set -e

cd "$(dirname "$0")"

D=":99"
export DISPLAY="$D"

# 启动 Xvfb 虚拟屏幕（未运行时）
if ! xdpyinfo -display "$D" >/dev/null 2>&1; then
    Xvfb "$D" -screen 0 1280x800x24 -nolisten tcp &
    sleep 1
fi

# 启动 openbox 窗口管理器（未运行时）
if ! pgrep -x openbox >/dev/null; then
    openbox &
    sleep 0.5
fi

# 启动基础终端应用（未运行时）
if ! pgrep -x xterm >/dev/null; then
    xterm -title webvnc -geometry 80x24+20+20 &
fi

# 前台运行 webvnc（抓取虚拟桌面）
exec python3 -u webvnc.py --port 6080 --vnc-port 5900 --xdisplay "$D"
