#!/usr/bin/env python3
"""
gui.py - BetterVNC 图形控制台（Tkinter）

功能：
  1. 启动/停止服务端（webvnc.py），实时查看服务端日志
  2. 查看服务端运行状态与开放端口（Web / VNC）
  3. 查看本机所有 IP，点击 IP 后的浏览器图标直接打开访问地址
  4. 模块管理：配置内置 Python 3.14 的模块（pip 安装 / 更新 / 从 whl 文件导入）
  5. 内置 CMD：执行命令并获取输出（无弹窗）

运行：python gui.py（推荐由 run.bat 使用内置 Python 启动）
"""
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
EMBED_DIR = os.path.join(BASE, "python")
IS_WINDOWS = (os.name == "nt")
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

# 浏览器小图标（16x16 地球，PNG base64，内嵌避免外部文件依赖）
_ICON_BROWSER_B64 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAxUlEQVR4nK1TsRHDIBCTuCzhJqU9goejNStkJnsEWhfOGEoB+IAQO7lYDccjPf+CJxqQJABLFR5JssV/E0ua+0nqJ0nSFtc5Ji5gKqEALIPDWBNjbMl4AABKepyWdQCm2wcXAt6WFXiL5+DQ1WfeAiRpjsStNrwN5g4uXGw+kb/F3wkoacv2K4D7iabg3AB0mQdrMiwhN7HmeHtBC4YkvQ2b3OUWWs94zUcC9gECcPyRgHCWBmv3gBFAu40kznhlBTl+GecXvdGHj/dm8mMAAAAASUVORK5CYII="

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog


def embedded_python():
    """内置嵌入式 Python 相对路径；不存在时回退当前解释器"""
    exe = os.path.join("python", "python.exe")
    if os.path.isfile(exe):
        return exe
    return sys.executable


def local_ips():
    """获取本机全部 IPv4 地址（去重，含回环地址置底）"""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips) + ["127.0.0.1"]


def port_open(port):
    """检测本机端口是否处于监听状态"""
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return True
    except OSError:
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.logq = queue.Queue()
        self.cmdq = queue.Queue()
        self.icon = tk.PhotoImage(data=_ICON_BROWSER_B64)

        root.title("BetterVNC 控制台")
        root.geometry("980x660")
        root.minsize(860, 560)

        main = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        main.add(self._build_left(main), weight=3)
        main.add(self._build_right(main), weight=2)

        self._refresh_status()
        self._poll_log()
        self._poll_cmd()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 界面构建 ----------------
    def _build_left(self, parent):
        frame = ttk.Frame(parent)
        box = ttk.Labelframe(frame, text="服务控制")
        box.pack(fill=tk.X, padx=4, pady=4)

        row1 = ttk.Frame(box)
        row1.pack(fill=tk.X, padx=6, pady=4)
        self.status_label = ttk.Label(row1, text="○ 已停止", foreground="#888")
        self.status_label.pack(side=tk.LEFT)
        ttk.Label(row1, text="    Web 端口:").pack(side=tk.LEFT)
        self.web_port = ttk.Entry(row1, width=7)
        self.web_port.insert(0, "6080")
        self.web_port.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(row1, text="VNC 端口:").pack(side=tk.LEFT)
        self.vnc_port = ttk.Entry(row1, width=7)
        self.vnc_port.insert(0, "5900")
        self.vnc_port.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(row1, text="访问令牌:").pack(side=tk.LEFT)
        self.token = ttk.Entry(row1, width=12, show="*")
        self.token.pack(side=tk.LEFT, padx=2)

        row2 = ttk.Frame(box)
        row2.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.btn_start = ttk.Button(row2, text="启动服务", command=self.start_server)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(row2, text="停止服务",
                                   command=self.stop_server, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Label(row2, text="（首次启动会自动联网安装 Pillow）",
                  foreground="#888").pack(side=tk.LEFT, padx=8)

        logbox = ttk.Labelframe(frame, text="服务端日志")
        logbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.log_text = scrolledtext.ScrolledText(
            logbox, height=14, state=tk.DISABLED, font=("Consolas", 10),
            wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        return frame

    def _build_right(self, parent):
        frame = ttk.Frame(parent)

        # ---- 本机访问地址 ----
        ipbox = ttk.Labelframe(frame, text="本机访问地址")
        ipbox.pack(fill=tk.X, padx=4, pady=4)
        head = ttk.Frame(ipbox)
        head.pack(fill=tk.X, padx=6, pady=(4, 0))
        ttk.Button(head, text="刷新", width=6,
                   command=self.refresh_ips).pack(side=tk.RIGHT)
        ttk.Label(head, text="点击 IP 后的图标在浏览器打开").pack(side=tk.LEFT)
        self.ip_list = ttk.Frame(ipbox)
        self.ip_list.pack(fill=tk.X, padx=6, pady=(2, 6))

        # ---- 模块管理 ----
        modbox = ttk.Labelframe(frame, text="模块管理（内置 Python 3.14）")
        modbox.pack(fill=tk.X, padx=4, pady=4)
        row1 = ttk.Frame(modbox)
        row1.pack(fill=tk.X, padx=6, pady=4)
        ttk.Label(row1, text="模块名:").pack(side=tk.LEFT)
        self.module_name = ttk.Entry(row1)
        self.module_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.module_name.insert(0, "pillow")
        row2 = ttk.Frame(modbox)
        row2.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(row2, text="安装", command=lambda: self.pip_op("install")).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(row2, text="更新", command=lambda: self.pip_op("upgrade")).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="卸载", command=lambda: self.pip_op("uninstall")).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="已安装列表", command=lambda: self.pip_op("list")).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="从文件导入...",
                   command=self.pip_install_file).pack(side=tk.LEFT, padx=4)

        # ---- 内置 CMD ----
        cmdbbox = ttk.Labelframe(frame, text="内置 CMD")
        cmdbbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.cmd_text = scrolledtext.ScrolledText(
            cmdbbox, height=9, state=tk.DISABLED, font=("Consolas", 10),
            wrap=tk.WORD)
        self.cmd_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        row = ttk.Frame(cmdbbox)
        row.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(row, text=">").pack(side=tk.LEFT)
        self.cmd_input = ttk.Entry(row)
        self.cmd_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.cmd_input.bind("<Return>", lambda e: self.run_cmd())
        ttk.Button(row, text="执行", command=self.run_cmd).pack(side=tk.LEFT)
        return frame

    # ---------------- 服务控制 ----------------
    def _append_log(self, line):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def start_server(self):
        if self.proc and self.proc.poll() is None:
            return
        web = self.web_port.get().strip() or "6080"
        vnc = self.vnc_port.get().strip() or "5900"
        token = self.token.get().strip()
        cmd = [embedded_python(), "-u", "webvnc.py",
               "--port", web, "--vnc-port", vnc]
        if token:
            cmd += ["--token", token]
        self._append_log(f"$ {' '.join(cmd)}")
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW)
        except OSError as exc:
            self._append_log(f"[启动失败] {exc}")
            return

        def reader():
            for line in self.proc.stdout:
                self.logq.put(line.rstrip("\r\n"))
            self.logq.put("[服务进程已退出]")
        threading.Thread(target=reader, daemon=True).start()

    def stop_server(self):
        if not self.proc or self.proc.poll() is not None:
            return
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        except OSError:
            pass

    def _refresh_status(self):
        running = bool(self.proc and self.proc.poll() is None)
        if running:
            web_ok = port_open(self.web_port.get().strip() or "6080")
            vnc_ok = port_open(self.vnc_port.get().strip() or "5900")
            self.status_label.configure(
                text=f"● 运行中    Web:{'监听中' if web_ok else '未监听'}    "
                     f"VNC:{'监听中' if vnc_ok else '未监听'}",
                foreground="#1a9c3a")
        else:
            self.status_label.configure(text="○ 已停止", foreground="#888")
        self.btn_start.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if running else tk.DISABLED)
        self.root.after(1000, self._refresh_status)

    def _poll_log(self):
        try:
            while True:
                self._append_log(self.logq.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._poll_log)

    # ---------------- 本机 IP ----------------
    def refresh_ips(self):
        for child in self.ip_list.winfo_children():
            child.destroy()
        port = self.web_port.get().strip() or "6080"
        for ip in local_ips():
            row = ttk.Frame(self.ip_list)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=ip, font=("Consolas", 10)).pack(side=tk.LEFT)
            btn = tk.Button(row, image=self.icon, bd=0, cursor="hand2",
                            command=lambda i=ip: self.open_browser(i))
            btn.pack(side=tk.LEFT, padx=6)
            ttk.Label(row, text=f"https://{ip}:{port}/vnc.html",
                      foreground="#888").pack(side=tk.LEFT)

    def open_browser(self, ip):
        port = self.web_port.get().strip() or "6080"
        url = f"https://{ip}:{port}/vnc.html"
        self._append_log(f"[打开浏览器] {url}")
        webbrowser.open(url)

    # ---------------- 模块管理 ----------------
    def _append_cmd(self, line):
        self.cmd_text.configure(state=tk.NORMAL)
        self.cmd_text.insert(tk.END, line + "\n")
        self.cmd_text.see(tk.END)
        self.cmd_text.configure(state=tk.DISABLED)

    def pip_op(self, op):
        args = None
        if op == "list":
            args = ["-m", "pip", "list"]
        else:
            name = self.module_name.get().strip()
            if not name:
                self._append_cmd("[提示] 请先输入模块名")
                return
            if op == "install":
                args = ["-m", "pip", "install", name]
            elif op == "upgrade":
                args = ["-m", "pip", "install", "--upgrade", name]
            elif op == "uninstall":
                args = ["-m", "pip", "uninstall", "-y", name]
        self._run_in_cmd([embedded_python()] + args)

    def pip_install_file(self):
        path = filedialog.askopenfilename(
            title="选择模块文件",
            filetypes=[("Python 模块包", "*.whl *.tar.gz *.zip"),
                       ("所有文件", "*.*")])
        if not path:
            return
        self._run_in_cmd([embedded_python(), "-m", "pip", "install", path])

    # ---------------- 内置 CMD ----------------
    def run_cmd(self):
        command = self.cmd_input.get().strip()
        if not command:
            return
        self.cmd_input.delete(0, tk.END)
        if IS_WINDOWS:
            cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", command]
        else:
            cmd = ["/bin/sh", "-c", command]
        self._run_in_cmd(cmd)

    def _run_in_cmd(self, cmd):
        self._append_cmd("$ " + subprocess.list2cmdline(cmd)
                         if IS_WINDOWS else " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", creationflags=NO_WINDOW)
        except OSError as exc:
            self._append_cmd(f"[启动失败] {exc}")
            return

        def reader(pid=proc):
            for line in proc.stdout:
                self.cmdq.put(line.rstrip("\r\n"))
            self.cmdq.put(f"[退出码 {proc.wait()}]")
        threading.Thread(target=reader, daemon=True).start()

    def _poll_cmd(self):
        try:
            while True:
                self._append_cmd(self.cmdq.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._poll_cmd)

    # ---------------- 退出 ----------------
    def _on_close(self):
        self.stop_server()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    app = App(root)
    app.refresh_ips()
    root.mainloop()


if __name__ == "__main__":
    main()
