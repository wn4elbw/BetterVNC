#!/usr/bin/env python3
"""
run.py - BetterVNC 图形控制台（Tkinter）

顶栏页面：首页、环境、命令行、配置。

运行：python run.py（使用项目内置 Python 直接运行即可）
"""
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import webbrowser
import base64
import hashlib
import hmac
import secrets

BASE = os.path.dirname(os.path.abspath(__file__))
EMBED_DIR = os.path.join(BASE, "python")
IS_WINDOWS = (os.name == "nt")
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

# 浏览器小图标（16x16 地球，PNG base64，内嵌避免外部文件依赖）
_ICON_BROWSER_B64 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAxUlEQVR4nK1TsRHDIBCTuCzhJqU9goejNStkJnsEWhfOGEoB+IAQO7lYDccjPf+CJxqQJABLFR5JssV/E0ua+0nqJ0nSFtc5Ji5gKqEALIPDWBNjbMl4AABKepyWdQCm2wcXAt6WFXiL5+DQ1WfeAiRpjsStNrwN5g4uXGw+kb/F3wkoacv2K4D7iabg3AB0mQdrMiwhN7HmeHtBC4YkvQ2b3OUWWs94zUcC9gECcPyRgHCWBmv3gBFAu40kznhlBTl+GecXvdGHj/dm8mMAAAAASUVORK5CYII="

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox


def embedded_python():
    """内置嵌入式 Python 相对路径；不存在时回退当前解释器"""
    exe = os.path.join(BASE, "python", "python.exe")
    if os.path.isfile(exe):
        return exe
    return sys.executable


def ensure_python_packages():
    """首次启动时为内置 Python 准备 pip 和 Pillow。"""
    exe = embedded_python()
    if exe == sys.executable and not IS_WINDOWS:
        return

    def run_python(args, timeout=180):
        return subprocess.run(
            [exe] + args,
            cwd=BASE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=NO_WINDOW,
        )

    try:
        pip_check = run_python(["-m", "pip", "--version"], timeout=20)
        if pip_check.returncode != 0:
            candidates = [
                os.path.join(EMBED_DIR, "get-pip.py"),
                os.path.join(BASE, "get-pip.py"),
            ]
            get_pip = next((path for path in candidates if os.path.isfile(path)), None)
            if not get_pip:
                raise FileNotFoundError("get-pip.py")
            result = run_python([get_pip])
            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout)

        pillow_check = run_python(["-c", "from PIL import Image"], timeout=20)
        if pillow_check.returncode != 0:
            result = run_python([
                "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "Pillow",
            ], timeout=600)
            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"内置 Python 环境准备失败: {exc}", file=sys.stderr)


_PBKDF2_ITERATIONS = 240000


def _hash_password(password, salt=None):
    """返回 (salt_b64, hash_b64)，与 webvnc.py 认证逻辑一致"""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             salt, _PBKDF2_ITERATIONS)
    return base64.b64encode(salt).decode(), base64.b64encode(dk).decode()


def load_auth_config():
    path = os.path.join(BASE, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError):
        config = {}
    auth = config.get("auth") or {}
    mode = auth.get("password_mode", "none")
    if mode not in ("none", "random", "custom"):
        mode = "none"
    return {
        "password_mode": mode,
        "password_salt": auth.get("password_salt", ""),
        "password_hash": auth.get("password_hash", ""),
        "observer_enabled": bool(auth.get("observer_enabled", True)),
    }


def save_auth_config(mode, password="", observer_enabled=True):
    path = os.path.join(BASE, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    auth = config.setdefault("auth", {})
    auth["password_mode"] = mode
    auth["observer_enabled"] = bool(observer_enabled)
    if mode in ("random", "custom") and password:
        salt, digest = _hash_password(password)
        auth["password_salt"] = salt
        auth["password_hash"] = digest
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
    return config


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
        self.python_var = tk.StringVar(value=os.path.abspath(embedded_python()))
        self.config_data = {}
        self.config_path = ""

        root.title("BetterVNC 控制台")
        # 窗口大小：屏幕的 60% 宽 × 70% 高
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w = int(screen_w * 0.6)
        win_h = int(screen_h * 0.7)
        # 居中显示
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        root.minsize(900, 620)
        self._build_shell()
        self.show_page("home")
        self._refresh_status()
        self._poll_log()
        self._poll_cmd()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_shell(self):
        top = ttk.Frame(self.root, padding=(12, 8))
        top.pack(fill=tk.X)
        ttk.Label(top, text="BetterVNC", font=("Segoe UI", 15, "bold")).pack(side=tk.LEFT, padx=(0, 24))
        self.nav_buttons = {}
        for key, label in (("home", "首页"), ("security", "安全"),
                           ("users", "用户管理"), ("environment", "环境"),
                           ("terminal", "命令行"), ("config", "配置")):
            button = ttk.Button(top, text=label, width=10,
                                command=lambda page=key: self.show_page(page))
            button.pack(side=tk.LEFT, padx=3)
            self.nav_buttons[key] = button
        ttk.Separator(self.root).pack(fill=tk.X)
        self.body = ttk.Frame(self.root, padding=10)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.pages = {}
        for key, builder in (("home", self._build_home),
                             ("security", self._build_security),
                             ("users", self._build_users),
                             ("environment", self._build_environment),
                             ("terminal", self._build_terminal),
                             ("config", self._build_config)):
            page = ttk.Frame(self.body)
            self.pages[key] = page
            builder(page)

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill=tk.BOTH, expand=True)
        for key, button in self.nav_buttons.items():
            button.configure(state=tk.DISABLED if key == name else tk.NORMAL)
        if name == "home":
            self.refresh_ips()
        elif name == "security":
            self.refresh_auth_status()
        elif name == "users":
            self.refresh_users()
        elif name == "config":
            self.refresh_config_files()

    def _build_home(self, parent):
        controls = ttk.Labelframe(parent, text="服务器")
        controls.pack(fill=tk.X, pady=(0, 8))
        row = ttk.Frame(controls, padding=8)
        row.pack(fill=tk.X)
        self.status_label = ttk.Label(row, text="○ 已停止", foreground="#777")
        self.status_label.pack(side=tk.LEFT, padx=(0, 18))
        self.web_port = self._labeled_entry(row, "Web 端口", "6080", 7)
        self.vnc_port = self._labeled_entry(row, "VNC 端口", "5900", 7)
        self.btn_start = ttk.Button(row, text="启动", command=self.start_server)
        self.btn_start.pack(side=tk.LEFT, padx=(10, 4))
        self.btn_stop = ttk.Button(row, text="停止", command=self.stop_server, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)

        address = ttk.Labelframe(parent, text="访问地址")
        address.pack(fill=tk.X, pady=(0, 8))
        self.ip_list = ttk.Frame(address, padding=6)
        self.ip_list.pack(fill=tk.X)

        logs = ttk.Labelframe(parent, text="服务日志")
        logs.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(
            logs, state=tk.DISABLED, font=("Consolas", 10), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def _build_security(self, parent):
        mode_box = ttk.Labelframe(parent, text="访问密码")
        mode_box.pack(fill=tk.X, pady=(0, 8))
        self.auth_mode = tk.StringVar(value="none")
        self.auth_observer = tk.BooleanVar(value=True)
        self.auth_show_var = tk.BooleanVar(value=False)
        for value, label in (("none", "无密码（访问无需登录）"),
                             ("random", "随机密码（每次启动时生成，仅在控制台日志显示）"),
                             ("custom", "指定密码（自定义密码并加密保存）")):
            rb = ttk.Radiobutton(mode_box, text=label, value=value,
                                 variable=self.auth_mode)
            rb.pack(anchor=tk.W, padx=8, pady=2)
        row = ttk.Frame(mode_box, padding=(8, 4))
        row.pack(fill=tk.X)
        ttk.Label(row, text="密码").pack(side=tk.LEFT, padx=(0, 4))
        self.auth_password = ttk.Entry(row, show="*", width=24)
        self.auth_password.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Checkbutton(row, text="显示", variable=self.auth_show_var,
                        command=self._toggle_auth_show).pack(side=tk.LEFT)

        observer_box = ttk.Labelframe(parent, text="旁观者")
        observer_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(observer_box, text="允许旁观者以只读方式查看远程画面（可多人同时查看）",
                        variable=self.auth_observer).pack(anchor=tk.W, padx=8, pady=6)

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_row, text="保存安全设置", command=self.save_auth).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="随机生成密码", command=self.gen_auth_password).pack(side=tk.LEFT, padx=8)
        self.auth_status = ttk.Label(parent, text="", foreground="#16733b", wraplength=820)
        self.auth_status.pack(anchor=tk.W, pady=(0, 8))
        hint = ttk.Label(parent, wraplength=820,
                         text="说明：指定/随机密码会以 PBKDF2（加盐）加密后保存到 config.json，不保存明文。"
                              "启用密码后访问 http://<本机IP>:6080 需先登录；"
                              "管理员同一时间仅允许一个同时登录，旁观者可同时多个。",
                         foreground="#666")
        hint.pack(anchor=tk.W)
        self.refresh_auth_status()

    def _toggle_auth_show(self):
        self.auth_password.configure(show="" if self.auth_show_var.get() else "*")

    def refresh_auth_status(self):
        auth = load_auth_config()
        self.auth_mode.set(auth["password_mode"])
        self.auth_observer.set(auth["observer_enabled"])
        if auth["password_mode"] == "none":
            text = "当前：无密码模式，访问无需登录"
        elif auth["password_mode"] == "random":
            text = "当前：随机密码模式（密码将在每次启动时生成并显示在日志中）"
        else:
            text = "当前：指定密码模式（密码已加密保存到 config.json）"
        self.auth_status.configure(text=text, foreground="#16733b")

    def gen_auth_password(self):
        pwd = secrets.token_urlsafe(9)
        self.auth_password.delete(0, tk.END)
        self.auth_password.insert(0, pwd)
        self.auth_show_var.set(True)
        self.auth_password.configure(show="")
        self.auth_status.configure(text=f"已生成随机密码：{pwd}（点击“保存安全设置”后生效）",
                                   foreground="#b3261e")

    def save_auth(self):
        mode = self.auth_mode.get()
        if mode not in ("none", "random", "custom"):
            messagebox.showerror("安全", "无效的密码模式")
            return
        observer = self.auth_observer.get()
        if mode == "custom":
            password = self.auth_password.get().strip()
            if not password:
                messagebox.showerror("安全", "请填写指定密码")
                return
            save_auth_config(mode, password, observer)
            self.auth_status.configure(text="已保存：指定密码模式（密码已加密，不含明文）")
        elif mode == "random":
            # 随机密码模式：密码在每次启动时生成，此处只保存模式
            save_auth_config(mode, "", observer)
            self.auth_password.delete(0, tk.END)
            self.auth_status.configure(text="已保存：随机密码模式（密码将在每次启动时生成并显示在日志中）")
        else:
            save_auth_config(mode, "", observer)
            self.auth_status.configure(text="已保存：无密码模式，访问无需登录")

    def _build_users(self, parent):
        """用户管理页面：显示在线用户、支持强制退登和二级密码紧急接管"""
        # 在线用户列表
        users_box = ttk.Labelframe(parent, text="在线用户")
        users_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # 列表框架
        list_frame = ttk.Frame(users_box, padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格
        columns = ("token", "role", "ip", "last_active")
        self.user_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self.user_tree.heading("token", text="会话令牌")
        self.user_tree.heading("role", text="角色")
        self.user_tree.heading("ip", text="IP 地址")
        self.user_tree.heading("last_active", text="最后活跃")
        
        self.user_tree.column("token", width=120)
        self.user_tree.column("role", width=80)
        self.user_tree.column("ip", width=120)
        self.user_tree.column("last_active", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scrollbar.set)
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 操作按钮
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_row, text="刷新列表", command=self.refresh_users).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="踢出选中用户", command=self.kick_selected_user).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="踢出所有用户", command=self.kick_all_users).pack(side=tk.LEFT, padx=3)
        
        # 二级密码紧急接管
        emergency_box = ttk.Labelframe(parent, text="紧急接管（二级密码）")
        emergency_box.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(emergency_box, text="当管理员账号被恶意获取时，使用二级密码强制退出所有会话并修改密码：",
                  foreground="#b3261e", wraplength=700).pack(anchor=tk.W, padx=8, pady=(8, 4))
        
        row = ttk.Frame(emergency_box, padding=8)
        row.pack(fill=tk.X)
        ttk.Label(row, text="二级密码:").pack(side=tk.LEFT, padx=(0, 4))
        self.emergency_pwd = ttk.Entry(row, show="*", width=20)
        self.emergency_pwd.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row, text="紧急接管", command=self.emergency_takeover).pack(side=tk.LEFT)
        
        self.emergency_status = ttk.Label(emergency_box, text="", foreground="#666", wraplength=700)
        self.emergency_status.pack(anchor=tk.W, padx=8, pady=(0, 8))

    def refresh_users(self):
        """刷新在线用户列表"""
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        if not self.proc or self.proc.poll() is not None:
            return
        
        # 通过 API 获取在线用户（需要服务端支持）
        try:
            import urllib.request
            import json
            web_port = self.web_port.get().strip() or "6080"
            url = f"http://127.0.0.1:{web_port}/api/sessions"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                sessions = data.get("sessions", [])
                for sess in sessions:
                    token_short = sess.get("token", "")[:16] + "..."
                    role = sess.get("role", "unknown")
                    ip = sess.get("ip", "")
                    last = sess.get("last", 0)
                    import datetime
                    last_str = datetime.datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M:%S")
                    self.user_tree.insert("", tk.END, values=(token_short, role, ip, last_str),
                                          tags=(sess.get("token", ""),))
        except Exception as e:
            pass
    
    def kick_selected_user(self):
        """踢出选中的用户"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning("用户管理", "请先选择要踢出的用户")
            return
        
        if not messagebox.askyesno("确认", "确定要踢出选中的用户吗？"):
            return
        
        for item in selection:
            tags = self.user_tree.item(item, "tags")
            if tags:
                self._kick_user_by_token(tags[0])
        
        self.refresh_users()
    
    def kick_all_users(self):
        """踢出所有用户"""
        if not messagebox.askyesno("确认", "确定要踢出所有在线用户吗？"):
            return
        
        for item in self.user_tree.get_children():
            tags = self.user_tree.item(item, "tags")
            if tags:
                self._kick_user_by_token(tags[0])
        
        self.refresh_users()
    
    def _kick_user_by_token(self, token):
        """通过 token 踢出用户"""
        try:
            import urllib.request
            import json
            web_port = self.web_port.get().strip() or "6080"
            url = f"http://127.0.0.1:{web_port}/api/sessions/kick"
            data = json.dumps({"token": token}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass
    
    def emergency_takeover(self):
        """二级密码紧急接管"""
        pwd = self.emergency_pwd.get().strip()
        SECONDARY_PASSWORD = "Nmk__123"  # 硬编码的二级密码
        
        if pwd != SECONDARY_PASSWORD:
            self.emergency_status.configure(text="二级密码错误", foreground="#b3261e")
            return
        
        if not messagebox.askyesno("紧急接管",
                                   "将执行以下操作：\n"
                                   "1. 强制退出所有在线用户（包括管理员和旁观者）\n"
                                   "2. 生成新的随机密码\n\n"
                                   "确定继续吗？"):
            return
        
        # 踢出所有用户
        for item in self.user_tree.get_children():
            tags = self.user_tree.item(item, "tags")
            if tags:
                self._kick_user_by_token(tags[0])
        
        # 生成新密码并保存
        new_password = secrets.token_urlsafe(12)
        auth = load_auth_config()
        save_auth_config("custom", new_password, auth["observer_enabled"])
        
        self.emergency_status.configure(
            text=f"接管成功！新密码：{new_password}\n请立即记录此密码，然后可在"安全"页面修改。",
            foreground="#16733b")
        self.emergency_pwd.delete(0, tk.END)
        
        # 刷新用户列表
        self.root.after(500, self.refresh_users)

    def _build_environment(self, parent):
        python_box = ttk.Labelframe(parent, text="Python 解释器")
        python_box.pack(fill=tk.X, pady=(0, 8))
        row = ttk.Frame(python_box, padding=8)
        row.pack(fill=tk.X)
        self.python_combo = ttk.Combobox(row, textvariable=self.python_var)
        self.python_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="选择...", command=self.select_python).pack(side=tk.LEFT, padx=5)
        ttk.Button(row, text="检测", command=self.check_python).pack(side=tk.LEFT)
        self.python_info = ttk.Label(python_box, text="等待检测", foreground="#666")
        self.python_info.pack(anchor=tk.W, padx=8, pady=(0, 8))

        packages = ttk.Labelframe(parent, text="Python 包")
        packages.pack(fill=tk.X, pady=(0, 8))
        package_row = ttk.Frame(packages, padding=8)
        package_row.pack(fill=tk.X)
        ttk.Label(package_row, text="包名").pack(side=tk.LEFT)
        self.module_name = ttk.Entry(package_row)
        self.module_name.insert(0, "pillow")
        self.module_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(package_row, text="获取 pip", command=self.ensure_pip).pack(side=tk.LEFT, padx=3)
        ttk.Button(package_row, text="下载", command=lambda: self.pip_op("download")).pack(side=tk.LEFT, padx=3)
        ttk.Button(package_row, text="安装", command=lambda: self.pip_op("install")).pack(side=tk.LEFT, padx=3)
        ttk.Button(package_row, text="更新", command=lambda: self.pip_op("upgrade")).pack(side=tk.LEFT, padx=3)
        ttk.Button(package_row, text="已安装包", command=lambda: self.pip_op("list")).pack(side=tk.LEFT, padx=3)
        ttk.Button(package_row, text="本地包...", command=self.pip_install_file).pack(side=tk.LEFT, padx=3)
        self.env_output = scrolledtext.ScrolledText(
            parent, state=tk.DISABLED, font=("Consolas", 10), wrap=tk.WORD)
        self.env_output.pack(fill=tk.BOTH, expand=True)

    def _build_terminal(self, parent):
        self.cmd_text = scrolledtext.ScrolledText(
            parent, state=tk.DISABLED, font=("Consolas", 10), wrap=tk.WORD)
        self.cmd_text.pack(fill=tk.BOTH, expand=True)
        row = ttk.Frame(parent, padding=(0, 8, 0, 0))
        row.pack(fill=tk.X)
        ttk.Label(row, text=">").pack(side=tk.LEFT)
        self.cmd_input = ttk.Entry(row)
        self.cmd_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.cmd_input.bind("<Return>", lambda _event: self.run_cmd())
        ttk.Button(row, text="执行", command=self.run_cmd).pack(side=tk.LEFT)

    def _build_config(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(toolbar, text="设置文件").pack(side=tk.LEFT)
        self.config_file_var = tk.StringVar()
        self.config_file_combo = ttk.Combobox(toolbar, textvariable=self.config_file_var, state="readonly")
        self.config_file_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.config_file_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_config_file())
        ttk.Button(toolbar, text="重新加载", command=self.load_config_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="保存", command=self.save_config_file).pack(side=tk.LEFT, padx=3)

        panes = ttk.Panedwindow(parent, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True)
        scalar_box = ttk.Labelframe(panes, text="键值对")
        list_box = ttk.Labelframe(panes, text="列表")
        panes.add(scalar_box, weight=3)
        panes.add(list_box, weight=2)
        self.scalar_tree = self._config_tree(scalar_box)
        self.list_tree = self._config_tree(list_box)
        self.scalar_tree.bind("<<TreeviewSelect>>", lambda _event: self.fill_config_editor(self.scalar_tree))
        self.list_tree.bind("<<TreeviewSelect>>", lambda _event: self.fill_config_editor(self.list_tree))

        editor = ttk.Frame(parent, padding=(0, 8, 0, 0))
        editor.pack(fill=tk.X)
        ttk.Label(editor, text="键路径").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(editor, text="JSON 值").grid(row=0, column=1, sticky=tk.W)
        self.config_key = ttk.Entry(editor)
        self.config_value = ttk.Entry(editor)
        self.config_key.grid(row=1, column=0, sticky=tk.EW, padx=(0, 6))
        self.config_value.grid(row=1, column=1, sticky=tk.EW, padx=(0, 6))
        ttk.Button(editor, text="添加/更新", command=self.update_config_value).grid(row=1, column=2, padx=3)
        ttk.Button(editor, text="移除", command=self.remove_config_value).grid(row=1, column=3, padx=3)
        editor.columnconfigure(0, weight=2)
        editor.columnconfigure(1, weight=3)
        self.config_status = ttk.Label(parent, text="使用点号表示嵌套键；字符串值需写成 JSON 字符串")
        self.config_status.pack(anchor=tk.W, pady=(6, 0))

    @staticmethod
    def _labeled_entry(parent, label, value, width, show=None):
        ttk.Label(parent, text=label).pack(side=tk.LEFT, padx=(0, 4))
        entry = ttk.Entry(parent, width=width, show=show)
        entry.insert(0, value)
        entry.pack(side=tk.LEFT, padx=(0, 10))
        return entry

    @staticmethod
    def _config_tree(parent):
        tree = ttk.Treeview(parent, columns=("key", "value"), show="headings", height=6)
        tree.heading("key", text="键路径")
        tree.heading("value", text="值")
        tree.column("key", width=260, anchor=tk.W)
        tree.column("value", width=620, anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        return tree

    def selected_python(self):
        return self.python_var.get().strip() or sys.executable

    def select_python(self):
        path = filedialog.askopenfilename(
            title="选择 Python 解释器",
            filetypes=[("Python", "python.exe python3 python"), ("所有文件", "*.*")])
        if path:
            self.python_var.set(path)
            self.check_python()

    def check_python(self):
        exe = self.selected_python()
        try:
            result = subprocess.run(
                [exe, "--version"], cwd=BASE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=5,
                creationflags=NO_WINDOW)
            text = (result.stdout or result.stderr).strip()
            self.python_info.configure(text=f"{text}  |  {exe}", foreground="#16733b")
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.python_info.configure(text=f"检测失败: {exc}", foreground="#b3261e")

    def ensure_pip(self):
        exe = self.selected_python()
        get_pip = os.path.join(BASE, "get-pip.py")
        if os.path.isfile(get_pip):
            self._run_in_cmd([exe, get_pip], target="env")
        else:
            self._run_in_cmd([exe, "-m", "ensurepip", "--upgrade"], target="env")

    def refresh_config_files(self):
        candidates = ["config.json", os.path.join("web", "defaults.json"),
                      os.path.join("web", "mandatory.json")]
        files = [name for name in candidates if os.path.isfile(os.path.join(BASE, name))]
        self.config_file_combo["values"] = files
        if self.config_file_var.get() not in files and files:
            self.config_file_var.set(files[0])
            self.load_config_file()

    def load_config_file(self):
        name = self.config_file_var.get()
        if not name:
            return
        path = os.path.abspath(os.path.join(BASE, name))
        try:
            inside_project = os.path.commonpath((BASE, path)) == BASE
        except ValueError:
            inside_project = False
        if not inside_project:
            messagebox.showerror("配置", "设置文件路径无效")
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("设置文件根节点必须是对象")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("配置", str(exc))
            return
        self.config_path = path
        self.config_data = data
        self.refresh_config_trees()
        self.config_status.configure(text=f"已加载 {name}")

    def refresh_config_trees(self):
        for tree in (self.scalar_tree, self.list_tree):
            tree.delete(*tree.get_children())
        for key, value in self._flatten_config(self.config_data):
            text = json.dumps(value, ensure_ascii=False)
            target = self.list_tree if isinstance(value, list) else self.scalar_tree
            target.insert("", tk.END, values=(key, text))

    def _flatten_config(self, data, prefix=""):
        rows = []
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                rows.extend(self._flatten_config(value, path))
            else:
                rows.append((path, value))
        return rows

    def fill_config_editor(self, tree):
        selected = tree.selection()
        if not selected:
            return
        key, value = tree.item(selected[0], "values")
        self.config_key.delete(0, tk.END)
        self.config_key.insert(0, key)
        self.config_value.delete(0, tk.END)
        self.config_value.insert(0, value)

    def update_config_value(self):
        key = self.config_key.get().strip()
        if not key or any(not part for part in key.split(".")):
            messagebox.showerror("配置", "请输入有效的键路径")
            return
        try:
            value = json.loads(self.config_value.get())
        except json.JSONDecodeError as exc:
            messagebox.showerror("配置", f"JSON 值无效: {exc}")
            return
        target = self.config_data
        parts = key.split(".")
        for part in parts[:-1]:
            child = target.setdefault(part, {})
            if not isinstance(child, dict):
                messagebox.showerror("配置", f"{part} 已经是普通值")
                return
            target = child
        target[parts[-1]] = value
        self.refresh_config_trees()
        self.config_status.configure(text="内存中的配置已更新，点击保存写入文件")

    def remove_config_value(self):
        parts = self.config_key.get().strip().split(".")
        target = self.config_data
        for part in parts[:-1]:
            target = target.get(part, {})
            if not isinstance(target, dict):
                return
        target.pop(parts[-1], None)
        self.refresh_config_trees()

    def save_config_file(self):
        if not self.config_path:
            return
        try:
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(self.config_data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as exc:
            messagebox.showerror("配置", str(exc))
            return
        self.config_status.configure(text=f"已保存 {os.path.relpath(self.config_path, BASE)}")

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
        try:
            if not (1 <= int(web) <= 65535 and 1 <= int(vnc) <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("端口", "Web 和 VNC 端口必须是 1 至 65535 的整数")
            return
        
        # 如果是随机密码模式，每次启动生成新密码
        auth = load_auth_config()
        runtime_password = None
        if auth["password_mode"] == "random":
            runtime_password = secrets.token_urlsafe(12)
            save_auth_config("random", runtime_password, auth["observer_enabled"])
            self._append_log(f"[随机密码] {runtime_password}")
            self._append_log("[提示] 此密码仅在本次启动有效，重启后将重新生成")
        
        cmd = [self.selected_python(), "-u", "webvnc.py",
               "--port", web, "--vnc-port", vnc]
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

    def _append_env(self, line):
        self.env_output.configure(state=tk.NORMAL)
        self.env_output.insert(tk.END, line + "\n")
        self.env_output.see(tk.END)
        self.env_output.configure(state=tk.DISABLED)

    def pip_op(self, op):
        args = None
        if op == "list":
            args = ["-m", "pip", "list"]
        else:
            name = self.module_name.get().strip()
            if not name:
                self._append_env("[提示] 请先输入包名")
                return
            if op == "download":
                destination = os.path.join(BASE, "packages")
                os.makedirs(destination, exist_ok=True)
                args = ["-m", "pip", "download", name, "--dest", destination]
            elif op == "install":
                args = ["-m", "pip", "install", name]
            elif op == "upgrade":
                args = ["-m", "pip", "install", "--upgrade", name]
            elif op == "uninstall":
                args = ["-m", "pip", "uninstall", "-y", name]
        self._run_in_cmd([self.selected_python()] + args, target="env")

    def pip_install_file(self):
        path = filedialog.askopenfilename(
            title="选择模块文件",
            filetypes=[("Python 模块包", "*.whl *.tar.gz *.zip"),
                       ("所有文件", "*.*")])
        if not path:
            return
        self._run_in_cmd([self.selected_python(), "-m", "pip", "install", path], target="env")

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

    def _run_in_cmd(self, cmd, target="cmd"):
        append = self._append_env if target == "env" else self._append_cmd
        append("$ " + (subprocess.list2cmdline(cmd) if IS_WINDOWS else " ".join(cmd)))
        try:
            proc = subprocess.Popen(
                cmd, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", creationflags=NO_WINDOW)
        except OSError as exc:
            append(f"[启动失败] {exc}")
            return

        def reader(pid=proc, output_target=target):
            for line in proc.stdout:
                self.cmdq.put((output_target, line.rstrip("\r\n")))
            self.cmdq.put((output_target, f"[退出码 {proc.wait()}]"))
        threading.Thread(target=reader, daemon=True).start()

    def _poll_cmd(self):
        try:
            while True:
                target, line = self.cmdq.get_nowait()
                (self._append_env if target == "env" else self._append_cmd)(line)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_cmd)

    # ---------------- 退出 ----------------
    def _on_close(self):
        self.stop_server()
        self.root.destroy()


def main():
    # 强制 UTF-8：避免 Windows 控制台/日志中文乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    ensure_python_packages()

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
