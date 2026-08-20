#!/usr/bin/env python3
"""
webvnc.py - BetterVNC 服务端（Windows 远程管理工具，单文件，自带 VNC Server）

功能：
  1. 自带纯 Python VNC Server（RFB 003.008 协议），共享本机屏幕，无密码
  2. HTTPS 文件管理器：左侧面板，从根目录浏览文件树，
     支持上传 / 下载 / 新建文件夹 / 改名 / 移动 / 打包 zip 下载
  3. 命令行终端：下方面板，直接执行命令并获取输出
  4. 内置网页客户端，打开即自动连接（无点击连接）

平台：Windows（共享真实屏幕并模拟键鼠输入）。
     非 Windows 环境自动切换为虚拟屏幕演示模式（便于调试预览）；
     指定 --xdisplay 时抓取 Linux 虚拟桌面（Xvfb）并模拟键鼠输入。

依赖：仅 Python 3 标准库 + Pillow（运行库）。
      pip install pillow
      Linux 虚拟桌面模式额外需要：Xvfb、openbox、xdotool、xterm

运行：python webvnc.py [--port 6080] [--vnc-port 5900] [--token xxx] [--xdisplay :99]
      Linux 虚拟桌面：bash run_desktop.sh

访问：https://<本机IP>:6080/vnc.html
"""
import argparse
import base64
import ctypes
import errno
import hashlib
import io
import json
import locale
import mimetypes
import os
import platform
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

# ---------------------------------------------------------------------------
# 内置自签名 HTTPS 证书（10 年期，CN=webvnc.local）
# ---------------------------------------------------------------------------
_TLS_CERT = """-----BEGIN CERTIFICATE-----
MIIDDzCCAfegAwIBAgIUR8lj7ur9YSLQwMlnsPaunjkMEaUwDQYJKoZIhvcNAQEL
BQAwFzEVMBMGA1UEAwwMd2Vidm5jLmxvY2FsMB4XDTI2MDgxODAyMTc0OFoXDTM2
MDgxNTAyMTc0OFowFzEVMBMGA1UEAwwMd2Vidm5jLmxvY2FsMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEArby5dP/JhOA/ZxjGCmTXUCcWMzWbBHjB5UGW
exHQXuxhWcgDkm1nfcjlvBHXu19iVUyh0mwvO4oOpamd/FvcynTWo+YbbvrUeUOB
Ux1Oop0xaUotWPeaFqd8PIqoR+jyzi6OcZcRjjq9Q1QMzoNxCZd9gMosw/BLBgWv
frAbx2iUAQFqQC9JKlhOyOom60s3WYnYWUy453pm/nSc+OJ4CEbcvXML7DwQx4vf
Q4Ong+Fu6HMSKzm68xPM1sgwakS2K1BYsaCogSOtUbk7moewr99Ifj73PUlkNgG1
itpn5TFKUFxriDtnpGj+2BbuRtMTTQkYTh2vvHAlGSK59P2jNQIDAQABo1MwUTAd
BgNVHQ4EFgQUaHwLBPbj6QXdltjiZB5wUJ0deLEwHwYDVR0jBBgwFoAUaHwLBPbj
6QXdltjiZB5wUJ0deLEwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOC
AQEAZQ7x4TEEfeonzh2up3vVFXvtjjKvA6ACSOkbf40b8/lbEm5aSo8S79cFuMMB
p14fXVWsOJvvlXTOPQK8qqciHI9Od3uFRSkUU7dmGjqXrRjaHwu+9N4MeulqZUwK
EL0O4PwDHdzi9too0FAw6xpDDr7YScRgwFQSwDPc3b+X/AZKLJw259wFKGoJqgnz
gd8ZNYeWLXaHuXbIMVion17ti7eArMAI8p4oygPzrsmk7MZiIB2HFoUc9jgKTF4G
kqvvWkMheBZ84akkWqloI7VfAbE1OJV1nlk6JT97wfvrIIltaz6yd61uK/inlhlW
UNfbvxUsxcszLWIXL27LsSwdzw==
-----END CERTIFICATE-----
"""
_TLS_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCtvLl0/8mE4D9n
GMYKZNdQJxYzNZsEeMHlQZZ7EdBe7GFZyAOSbWd9yOW8Ede7X2JVTKHSbC87ig6l
qZ38W9zKdNaj5htu+tR5Q4FTHU6inTFpSi1Y95oWp3w8iqhH6PLOLo5xlxGOOr1D
VAzOg3EJl32AyizD8EsGBa9+sBvHaJQBAWpAL0kqWE7I6ibrSzdZidhZTLjnemb+
dJz44ngIRty9cwvsPBDHi99Dg6eD4W7ocxIrObrzE8zWyDBqRLYrUFixoKiBI61R
uTuah7Cv30h+Pvc9SWQ2AbWK2mflMUpQXGuIO2ekaP7YFu5G0xNNCRhOHa+8cCUZ
Irn0/aM1AgMBAAECggEAJK3PSZAm71KYkB9+z/ryKg3WdgE/NPZ5mPj72AeuwhuN
gfLkLinCy596QPZTYU+F5xRCpbYJUryW0wq4O+r49hUsq3WNHST/bop95xos28/r
+pqacEn10gqSBAYR+PyJJlZV5E1Me4aTJn+8JG1DlA7ThDkqskMs05ynrEtp0fM8
7qppl7eNyZZMrZ3+vHB/2zwlG5WewyavL0U7Ovonrr02jEc46AjrSEAIU1nxfRZi
77Lv22lB87fVoh/R7wzlwv9zTnTbBjawpzhaSz+xgt9q5HCKRUr5K1OdOTgrvl21
qdFZLlf0y3hCvQV4Zs/ylx7n6tocQdeEcGyy2jzgAQKBgQDhJ4+DB6otjnQnl7xz
1I6sMZEmbJv9blOpOoNwk2qzyKo0iH2xtKbIsUw5cMT3aIDDEGkT8HCUdag7YZfw
mLkmlpXSQoNTcu3N/LINYGVY0v+MIvnAnTI/Be2TH1XWfDN1Nu83bfQkmyWPR4h9
ZIVEGIIlfIxBeRE/0ohJKcZyAQKBgQDFieWAdKsx8FW3XWMN2pSllSLM3oEGzQ09
GaNE0NSZhzykepGjpgvIscGGO4A1RMBdk7F8TIcIyz7XXF5IRsxg4fjyYQy6Barn
JE+bsetXAE63xUNQH/TVSeTCCzSLqhfiIkCFJixDo43sP10fw5VZ18PgW48UMa+/
A4eB6OYJNQKBgEfhtGyVttwCfcziIZUtSDtrO7bzt71qSqVde/cl6UvqhYRuCwr/
7Ltn9zjjas69+1XLWHC4M4kCIyqKFtMGPx41tzFAcOLkb01zHnkszE5WVqWryOaY
iSEbyGRO/b2TO25xkl+059wD+DLNGKNHw1AhLvO+1pxUhZBFq6MIBkYBAoGBAIVa
8X+Fw6jj+cnfFqbcoCskgijSMUK5HS3ZZ/pmDJBU1uCnCjjzONNVBTOsaYIMltzV
fyVNuH98TkEvT0r12LWy99ARKnlOqDCAt+mA9EJ4p6uyVR37ZNq0luVUkTWUL6lu
vCXnPkyvVnld0W1HKUVMvyRwSygz3tRR+qH964XdAoGBAL10Zb8xETzGXrUHUAbe
J2EXdTHWHHtni1BZgcN2TFkc74X6uuFpQQPDDMk6nQRag3hkRUhwT5hdjmDbNrCI
TYwjzobhqWkiQxGB68yROllKY/VfhGGHpvLxX16gekrbFlD5LVxVjBKRLMMIDtGx
gz7yyxxhx6BAXfobw5EP+4a3
-----END PRIVATE KEY-----
"""

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 65536
IS_WINDOWS = (os.name == "nt")


BASE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = "log"  # 相对路径，main() 中先切换到脚本目录
THEME_FILE = "theme.json"  # 界面主题配置文件（深色/浅色）
_log_lock = threading.Lock()
_log_file = None       # 当前日志文件（时间戳命名）
_log_last_clean = 0.0  # 上次清理旧日志时间（每天清理前一天）
_clip_display = None   # Linux 剪贴板使用的 X display（--xdisplay）


def _new_log_file():
    """创建新的日志文件（以时间戳为文件名），供启动与网页清屏调用"""
    global _log_file
    os.makedirs(LOG_DIR, exist_ok=True)
    _log_file = os.path.join(
        LOG_DIR, f"webvnc_{time.strftime('%Y%m%d_%H%M%S')}.log")
    with open(_log_file, "w", encoding="utf-8") as fh:
        fh.write(f"[{time.strftime('%H:%M:%S')}] [webvnc] 日志文件创建\n")
    return _log_file


def _clean_old_logs():
    """删除前一天及更早的日志文件（文件名含日期，每天清理一次）"""
    global _log_last_clean
    now = time.time()
    if now - _log_last_clean < 3600:
        return
    _log_last_clean = now
    today = time.strftime("%Y%m%d")
    try:
        for name in os.listdir(LOG_DIR):
            if not (name.startswith("webvnc_") and name.endswith(".log")):
                continue
            # 兼容新旧文件名：webvnc_YYYY-MM-DD.log / webvnc_YYYYmmdd_HHMMSS.log
            stamp = name[len("webvnc_"):-len(".log")].split("_")[0].replace("-", "")
            if len(stamp) == 8 and stamp.isdigit() and stamp < today:
                try:
                    os.remove(os.path.join(LOG_DIR, name))
                except OSError:
                    pass
    except OSError:
        pass


def load_theme():
    """读取界面主题配置，默认深色"""
    try:
        with open(THEME_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
            if d.get("theme") in ("dark", "light"):
                return d["theme"]
    except (OSError, ValueError):
        pass
    return "dark"


def save_theme(theme):
    """保存界面主题配置到文件"""
    if theme not in ("dark", "light"):
        theme = "dark"
    with open(THEME_FILE, "w", encoding="utf-8") as fh:
        json.dump({"theme": theme}, fh)


ENCODER_FILE = "encoder.json"  # 传输编码配置
_ENCODERS = ("zlib", "hextile", "raw")


def load_encoder():
    """读取传输编码配置，默认 zlib"""
    try:
        with open(ENCODER_FILE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
            if d.get("encoder") in _ENCODERS:
                return d["encoder"]
    except (OSError, ValueError):
        pass
    return "zlib"


def save_encoder(encoder):
    """保存传输编码配置到文件"""
    if encoder not in _ENCODERS:
        encoder = "zlib"
    with open(ENCODER_FILE, "w", encoding="utf-8") as fh:
        json.dump({"encoder": encoder}, fh)


def _hex_to_ip(hex_ip, is_v6=False):
    """把 /proc/net/tcp(6) 的十六进制地址转成可读 IP。
    tcp 是 1 个 32 位小端字（8 hex），tcp6 是 4 组 32 位小端字（32 hex）。"""
    try:
        if is_v6:
            # IPv4-mapped IPv6 (::ffff:a.b.c.d)：word2=0000FFFF，word3 为 IPv4 小端
            if len(hex_ip) == 32 and hex_ip[16:24] == "0000ffff":
                return _hex_to_ip(hex_ip[24:], False)
            parts = []
            for i in range(0, len(hex_ip), 8):
                word = int(hex_ip[i:i + 8], 16)
                parts.append(struct.pack(">I", word))  # 先恢复字节序
            raw = b"".join(parts)
            addr = socket.inet_ntop(socket.AF_INET6, raw)
            # IPv4-mapped (::ffff:a.b.c.d) 显示为 IPv4
            if addr.startswith("::ffff:"):
                return addr.rsplit(":", 1)[-1]
            return addr
        else:
            # /proc/net/tcp 的 8 hex 是小端序 32 位 IPv4
            v = int(hex_ip, 16)
            return f"{(v & 0xff)}.{((v >> 8) & 0xff)}.{((v >> 16) & 0xff)}.{((v >> 24) & 0xff)}"
    except Exception:
        return hex_ip


def get_netstat():
    """扫描本机所有处于监听状态的开放端口"""
    ports = []
    if IS_WINDOWS:
        try:
            out = subprocess.run(
                ["netstat", "-an"], capture_output=True, text=True,
                timeout=10, creationflags=NO_WINDOW).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[3].upper() == "LISTENING":
                    proto = parts[0].lower()
                    local = parts[1]
                    try:
                        port = int(local.rsplit(":", 1)[-1])
                    except ValueError:
                        continue
                    ports.append({"proto": proto, "addr": local, "port": port})
        except Exception:
            pass
    else:
        for fname in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(fname, "r", encoding="utf-8") as fh:
                    next(fh, None)
                    for line in fh:
                        f = line.split()
                        if len(f) < 4 or f[3] != "0A":
                            continue
                        hex_ip, _, hexport = f[1].rpartition(":")
                        try:
                            port = int(hexport, 16)
                        except ValueError:
                            continue
                        addr = _hex_to_ip(hex_ip, fname.endswith("tcp6"))
                        ports.append({"proto": "tcp", "addr": addr, "port": port})
            except OSError:
                pass
    seen = set()
    result = []
    for p in sorted(ports, key=lambda x: (x["port"], x["proto"], x["addr"])):
        key = (p["proto"], p["port"], p["addr"])
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# 系统占用统计（被预览机 CPU / 内存 / 磁盘 / 交换），供左下「负载」面板 1s 刷新
# Linux 解析 /proc；Windows 用 ctypes（GetSystemTimes / GlobalMemoryStatusEx）
# ---------------------------------------------------------------------------
_cpu_prev = None  # (jiffies_total, jiffies_idle) 上次采样，用于计算 CPU 使用率
_main_args = None  # main() 解析的启动参数，供 /api/power 重启服务


def _cpu_linux():
    """解析 /proc/stat 首个 cpu 行，返回 (total, idle) jiffies；失败返回 None"""
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            first = fh.readline()
        if not first.startswith("cpu "):
            return None
        vals = [int(v) for v in first.split()[1:]]
        total = sum(vals)
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return total, idle
    except Exception:
        return None


def get_system_stats():
    """返回被预览机系统占用字典：cpu_percent/mem/mem_percent/swap/disk 等"""
    global _cpu_prev
    stats = {
        "cpu_percent": None,
        "cpu_cores": None,
        "mem_total": None,
        "mem_used": None,
        "mem_percent": None,
        "swap_total": None,
        "swap_used": None,
        "swap_percent": None,
        "disk_total": None,
        "disk_used": None,
        "disk_percent": None,
        "hostname": None,
        "uptime": None,
        "loadavg": None,
        "platform": sys.platform,
    }
    try:
        stats["hostname"] = socket.gethostname()
    except Exception:
        pass

    if IS_WINDOWS:
        try:
            import ctypes
            # 内存
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                stats["mem_total"] = m.ullTotalPhys
                stats["mem_used"] = m.ullTotalPhys - m.ullAvailPhys
                stats["mem_percent"] = round(m.dwMemoryLoad, 1)
            # CPU（GetSystemTimes）
            _get_system_times = ctypes.windll.kernel32.GetSystemTimes
            idle = ctypes.c_ulonglong()
            kernel = ctypes.c_ulonglong()
            user = ctypes.c_ulonglong()
            if _get_system_times(ctypes.byref(idle), ctypes.byref(kernel),
                                 ctypes.byref(user)):
                cur_total = kernel.value + user.value
                cur_idle = idle.value
                if _cpu_prev:
                    d_total = cur_total - _cpu_prev[0]
                    d_idle = cur_idle - _cpu_prev[1]
                    if d_total > 0:
                        stats["cpu_percent"] = round(
                            max(0.0, min(100.0, (1 - d_idle / d_total) * 100)), 1)
                _cpu_prev = (cur_total, cur_idle)
        except Exception:
            pass
    else:
        try:
            cur = _cpu_linux()
            if cur:
                if _cpu_prev:
                    d_total = cur[0] - _cpu_prev[0]
                    d_idle = cur[1] - _cpu_prev[1]
                    if d_total > 0:
                        stats["cpu_percent"] = round(
                            max(0.0, min(100.0, (1 - d_idle / d_total) * 100)), 1)
                _cpu_prev = cur
            stats["cpu_cores"] = os.cpu_count()
            try:
                with open("/proc/loadavg", "r", encoding="utf-8") as fh:
                    la = fh.read().split()
                if la:
                    stats["loadavg"] = " ".join(la[:3])
            except OSError:
                pass
            try:
                with open("/proc/uptime", "r", encoding="utf-8") as fh:
                    stats["uptime"] = float(fh.read().split()[0])
            except OSError:
                pass
            meminfo = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split(":")
                    if len(parts) == 2:
                        val = parts[1].strip().split()[0]
                        try:
                            meminfo[parts[0]] = int(val) * 1024
                        except (ValueError, IndexError):
                            pass
            total = meminfo.get("MemTotal")
            avail = meminfo.get("MemAvailable", meminfo.get("MemFree"))
            if total:
                stats["mem_total"] = total
                used = total - avail if avail else None
                stats["mem_used"] = used
                if used is not None:
                    stats["mem_percent"] = round(used / total * 100, 1)
            sw_total = meminfo.get("SwapTotal") or 0
            sw_free = meminfo.get("SwapFree") or 0
            stats["swap_total"] = sw_total
            stats["swap_used"] = max(0, sw_total - sw_free)
            if sw_total:
                stats["swap_percent"] = round(stats["swap_used"] / sw_total * 100, 1)
        except Exception:
            pass

    # 磁盘（数据盘，取第一个根分区）
    try:
        if IS_WINDOWS:
            import ctypes
            free = ctypes.c_ulonglong()
            total_d = ctypes.c_ulonglong()
            if ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p("C:\\"), None, ctypes.byref(total_d),
                    ctypes.byref(free)):
                stats["disk_total"] = total_d.value
                stats["disk_used"] = total_d.value - free.value
        else:
            st = os.statvfs("/")
            total_d = st.f_frsize * st.f_blocks
            free_d = st.f_frsize * st.f_bavail
            stats["disk_total"] = total_d
            stats["disk_used"] = total_d - free_d
        if stats["disk_total"]:
            stats["disk_percent"] = round(
                stats["disk_used"] / stats["disk_total"] * 100, 1)
    except Exception:
        pass
    return stats


def restart_service():
    """重启 webvnc 服务进程（携带原启动参数，绝对路径，Windows 兼容）"""
    args = ["python" if IS_WINDOWS else "python3", os.path.abspath(__file__)]
    a = _main_args
    if a:
        if a.host != "0.0.0.0":
            args += ["--host", str(a.host)]
        if a.port != 6080:
            args += ["--port", str(a.port)]
        if a.vnc_host != "0.0.0.0":
            args += ["--vnc-host", str(a.vnc_host)]
        if a.vnc_port != 5900:
            args += ["--vnc-port", str(a.vnc_port)]
        if a.token:
            args += ["--token", a.token]
        if a.no_https:
            args += ["--no-https"]
        if a.xdisplay:
            args += ["--xdisplay", a.xdisplay]
    try:
        log("服务重启中 ...")
        subprocess.Popen(args, cwd=BASE, creationflags=NO_WINDOW)
        # 给新进程短暂启动时间后退出当前进程
        threading.Thread(target=_die_later, daemon=True).start()
        return True
    except Exception as exc:
        log(f"重启失败: {exc!r}")
        return False


def _die_later():
    time.sleep(1.5)
    os._exit(0)


def power_action(action):
    """电源控制：shutdown / reboot / restart_service"""
    if action == "restart_service":
        return restart_service()
    if action not in ("shutdown", "reboot"):
        return False
    try:
        if IS_WINDOWS:
            flag = 0x00000002 if action == "reboot" else 0x00000001
            import ctypes
            # SE_SHUTDOWN_NAME 提权后关机/重启
            ctypes.windll.ntdll.RtlAdjustPrivilege(
                19, 1, 0, ctypes.byref(ctypes.c_ulong()))
            ctypes.windll.user32.ExitWindowsEx(
                flag | 0x00000004, 0)  # EWX_REBOOT|EWX_POWEROFF|EWX_FORCE
            return True
        else:
            cmd = ["shutdown", "-r", "now"] if action == "reboot" else \
                ["shutdown", "-h", "now"]
            subprocess.Popen(cmd, cwd=BASE)
            return True
    except Exception as exc:
        log(f"电源操作失败: {exc!r}")
        return False


def log(msg):
    """输出到控制台，并保存到当前时间戳日志文件（行内仅时间不含日期）"""
    line = f"[{time.strftime('%H:%M:%S')}] [webvnc] {msg}"
    print(line, flush=True)
    try:
        with _log_lock:
            if _log_file is None:
                _new_log_file()
            _clean_old_logs()
            with open(_log_file, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError:
        pass


# Windows 下 subprocess 防止弹出控制台窗口的标志
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


# ---------------------------------------------------------------------------
# 依赖自检：缺少 Pillow 时自动安装 pip + Pillow 并重启进程
# ---------------------------------------------------------------------------
def _valid_python_source(path):
    """校验文件是完整可编译的 Python 源码（避免半截下载的损坏文件）"""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        compile(data, path, "exec")
        return True
    except Exception:
        return False


def _download_file(url, dest, tries=3):
    """下载文件并校验完整性：Content-Length 匹配 + Python 源码可编译"""
    import urllib.request
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                total = resp.headers.get("Content-Length")
                data = resp.read()
            if total:
                try:
                    total = int(total)
                except ValueError:
                    total = None
            if total is not None and len(data) != total:
                raise IOError(f"下载不完整: 仅收到 {len(data)}/{total} 字节")
            compile(data, dest, "exec")
            with open(dest, "wb") as fh:
                fh.write(data)
            return True
        except Exception as exc:
            log(f"下载 {os.path.basename(dest)} 失败（第 {attempt}/{tries} 次）: {exc}")
            try:
                os.remove(dest)
            except OSError:
                pass
    return False


def ensure_dependencies():
    try:
        import PIL  # noqa: F401
        return
    except ImportError:
        pass

    base = os.path.dirname(os.path.abspath(__file__))
    py = sys.executable
    log(f"未检测到运行库 Pillow，开始自动安装（需要联网）...")
    log(f"解释器: {py}")
    log(f"项目目录: {base}")

    def run_quiet(cmd, timeout=600):
        return subprocess.run(cmd, capture_output=True, text=True,
                              creationflags=NO_WINDOW, timeout=timeout)

    # 1. 确认 pip 可用，嵌入式 Python 首次运行需要先引导 pip
    log("步骤 1/3：检查 pip 是否可用 ...")
    try:
        probe = run_quiet([py, "-m", "pip", "--version"], timeout=60)
    except subprocess.TimeoutExpired:
        log("pip 探测超时，视为不可用")
        probe = type("R", (), {"returncode": -1})()
    log(f"pip 探测: {'可用 ' + (probe.stdout or '').strip() if probe.returncode == 0 else '不可用'}")
    if probe.returncode != 0:
        get_pip = os.path.join(base, "get-pip.py")
        if not (os.path.exists(get_pip) and _valid_python_source(get_pip)):
            log("步骤 1.1：下载 get-pip.py ...")
            if not _download_file(
                    "https://bootstrap.pypa.io/get-pip.py", get_pip):
                log("请手动将 get-pip.py 放入程序目录后重试")
                sys.exit(1)
            log(f"get-pip.py 就绪: {os.path.getsize(get_pip)} 字节")
        log("步骤 1.2：引导安装 pip ...")
        try:
            res = run_quiet([py, get_pip, "--no-warn-script-location"])
        except subprocess.TimeoutExpired:
            log("pip 引导超时")
            sys.exit(1)
        if res.returncode != 0:
            log(f"pip 安装失败: {(res.stderr or res.stdout or '').strip()}")
            sys.exit(1)
        log("pip 引导安装完成")

    # 2. 安装 Pillow
    log("步骤 2/3：安装 Pillow ...")
    try:
        res = run_quiet([py, "-m", "pip", "install", "--no-warn-script-location",
                         "pillow"])
    except subprocess.TimeoutExpired:
        log("Pillow 安装超时")
        sys.exit(1)
    if res.returncode != 0:
        log(f"Pillow 安装失败: {(res.stderr or res.stdout or '').strip()}")
        sys.exit(1)
    log(f"Pillow 安装完成: {(res.stdout or '').strip().splitlines()[-1] if (res.stdout or '').strip() else ''}")

    # 3. 重启自身，重新加载已安装的模块（绝对路径，Windows 兼容）
    log("步骤 3/3：重启服务以加载新模块 ...")
    try:
        py_abs = os.path.abspath(sys.executable)
        script = os.path.join(base, "webvnc.py")
        args = [py_abs, "-u", script] + sys.argv[1:]
        subprocess.Popen(args, cwd=base, creationflags=NO_WINDOW)
        log(f"已重新启动: {' '.join(args)}")
    except Exception as exc:
        log(f"重启失败: {exc!r}")
    os._exit(0)


# ---------------------------------------------------------------------------
# WebSocket 帧工具（复用自 websockify 逻辑）
# ---------------------------------------------------------------------------
class WebSocketError(Exception):
    pass


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise WebSocketError("connection closed")
        data += chunk
    return data


def recv_frame(sock):
    b0, b1 = recv_exact(sock, 2)
    opcode = b0 & 0x0F
    masked = (b1 >> 7) & 0x01
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack("!H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", recv_exact(sock, 8))[0]
    mask = recv_exact(sock, 4) if masked else None
    payload = recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def send_frame(sock, opcode, payload=b""):
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    sock.sendall(bytes(header) + payload)


# ---------------------------------------------------------------------------
# 屏幕抓取
# ---------------------------------------------------------------------------
class ScreenGrabber:
    """Windows 抓真实屏幕；Linux 指定 --xdisplay 时抓 X 虚拟桌面；
    否则生成虚拟画面便于调试预览。"""

    def __init__(self, xdisplay=None):
        self._lock = threading.Lock()
        self._t0 = time.time()
        self._xdisplay = xdisplay
        if IS_WINDOWS and Image is not None:
            self.virtual = False
        elif xdisplay:
            self.virtual = False
        else:
            self.virtual = True

    def grab(self):
        if self.virtual:
            return self._virtual_frame()
        from PIL import ImageGrab
        if self._xdisplay:
            img = ImageGrab.grab(xdisplay=self._xdisplay)
        else:
            img = ImageGrab.grab()
        try:
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception:
            pass
        return img

    def _virtual_frame(self):
        from PIL import ImageDraw as _Draw
        w, h = 1280, 800
        img = Image.new("RGB", (w, h), (28, 30, 52))
        draw = _Draw.Draw(img)
        t = time.time() - self._t0
        bx = int((t * 80) % (w - 140))
        by = int((t * 60) % (h - 140))
        draw.rectangle([bx, by, bx + 100, by + 80], fill=(58, 130, 220))
        draw.text((12, 10), time.strftime("%Y-%m-%d %H:%M:%S"), fill=(255, 255, 255))
        draw.text((12, 36), "webvnc virtual screen (demo mode)", fill=(180, 190, 210))
        return img


# ---------------------------------------------------------------------------
# VNC 输入模拟（Windows 通过 ctypes 调用 user32）
# ---------------------------------------------------------------------------
_KEYSYM_VK = {
    0xFF08: 0x08, 0xFF09: 0x09, 0xFF0D: 0x0D, 0xFF1B: 0x1B, 0xFFFF: 0x2E,
    0xFF50: 0x24, 0xFF51: 0x25, 0xFF52: 0x26, 0xFF53: 0x27, 0xFF54: 0x28,
    0xFF55: 0x21, 0xFF56: 0x22, 0xFF57: 0x23, 0xFFE1: 0x10, 0xFFE2: 0x10,
    0xFFE3: 0x11, 0xFFE4: 0x11, 0xFFE9: 0x12, 0xFFEA: 0x12, 0xFFE5: 0x14,
    0xFFE7: 0x5B, 0xFFE8: 0x5C, 0xFF61: 0x2D, 0xFF63: 0x2D, 0xFF20: 0x91,
    0xFFBE: 0x70, 0xFFBF: 0x71, 0xFFC0: 0x72, 0xFFC1: 0x73, 0xFFC2: 0x74,
    0xFFC3: 0x75, 0xFFC4: 0x76, 0xFFC5: 0x77, 0xFFC6: 0x78, 0xFFC7: 0x79,
    0xFFC8: 0x7A, 0xFFC9: 0x7B,
}


def keysym_to_vk(keysym):
    if keysym in _KEYSYM_VK:
        return _KEYSYM_VK[keysym]
    if 0x61 <= keysym <= 0x7A:
        return keysym - 0x20
    if 0x30 <= keysym <= 0x39:
        return keysym
    if 0x20 == keysym:
        return 0x20
    punct = {0x3B: 0xBA, 0x3D: 0xBB, 0x2C: 0xBC, 0x2D: 0xBD, 0x2E: 0xBE,
             0x2F: 0xBF, 0x60: 0xC0, 0x5B: 0xDB, 0x5C: 0xDC, 0x5D: 0xDD,
             0x27: 0xDE}
    return punct.get(keysym)


class WindowsInput:
    """Windows 鼠标 / 键盘输入模拟。"""

    def __init__(self):
        self._u = ctypes.windll.user32
        self._prev_buttons = 0
        self._lock = threading.Lock()

    def pointer(self, x, y, mask):
        with self._lock:
            self._u.SetCursorPos(int(x), int(y))
            actions = [
                (0x0001, 0x0002, 0x0004),
                (0x0004, 0x0020, 0x0040),
                (0x0002, 0x0008, 0x0010),
            ]
            for bit, down, up in actions:
                pressed = bool(mask & bit)
                was = bool(self._prev_buttons & bit)
                if pressed and not was:
                    self._u.mouse_event(down, 0, 0, 0, 0)
                elif was and not pressed:
                    self._u.mouse_event(up, 0, 0, 0, 0)
            if (mask & 0x0008) and not (self._prev_buttons & 0x0008):
                self._u.mouse_event(0x0800, 0, 0, 120, 0)
            if (mask & 0x0010) and not (self._prev_buttons & 0x0010):
                self._u.mouse_event(0x0800, 0, 0, -120, 0)
            self._prev_buttons = mask

    def key(self, keysym, down):
        vk = keysym_to_vk(keysym)
        if vk is None:
            return
        flags = 0 if down else 0x0002
        with self._lock:
            self._u.keybd_event(vk, 0, flags, 0)


class NullInput:
    def pointer(self, x, y, mask):
        pass

    def key(self, keysym, down):
        pass


# Linux X 虚拟桌面的键鼠映射（keysym -> xdotool 名称）
_KEYSYM_X = {
    0xFF08: "BackSpace", 0xFF09: "Tab", 0xFF0D: "Return", 0xFF1B: "Escape",
    0xFF50: "Home", 0xFF51: "Left", 0xFF52: "Up", 0xFF53: "Right",
    0xFF54: "Down", 0xFF55: "Page_Up", 0xFF56: "Page_Down", 0xFF57: "End",
    0xFF63: "Insert", 0xFFFF: "Delete",
    0xFFE1: "Shift_L", 0xFFE2: "Shift_R", 0xFFE3: "Control_L",
    0xFFE4: "Control_R", 0xFFE9: "Alt_L", 0xFFEA: "Alt_R",
    0xFFE7: "Super_L", 0xFFE8: "Super_R",
    0x20: "space",
    0x2C: "comma", 0x2D: "minus", 0x2E: "period", 0x2F: "slash",
    0x3B: "semicolon", 0x27: "apostrophe", 0x5B: "bracketleft",
    0x5C: "backslash", 0x5D: "bracketright", 0x60: "grave",
    0x3D: "equal", 0x2B: "plus", 0x2A: "asterisk",
}
for _i in range(12):
    _KEYSYM_X[0xFFBE + _i] = "F%d" % (_i + 1)


def keysym_to_xdotool(keysym):
    if keysym in _KEYSYM_X:
        return _KEYSYM_X[keysym]
    if 0x30 <= keysym <= 0x39 or 0x61 <= keysym <= 0x7A:
        return chr(keysym)
    return None


class XInput:
    """Linux X 虚拟桌面输入模拟（通过 xdotool，异步执行不阻塞 VNC 服务）"""

    def __init__(self, xdisplay):
        self._display = xdisplay
        self._prev_buttons = 0
        self._queue = []
        self._latest_xy = None
        self._cond = threading.Condition()
        threading.Thread(target=self._worker, daemon=True).start()

    def _run(self, args):
        env = dict(os.environ)
        env["DISPLAY"] = self._display
        try:
            subprocess.run(["xdotool"] + args, env=env,
                           capture_output=True, timeout=5)
        except Exception:
            pass

    def _worker(self):
        while True:
            with self._cond:
                while not self._queue and self._latest_xy is None:
                    self._cond.wait()
                ops = list(self._queue)
                self._queue.clear()
                xy = self._latest_xy
                self._latest_xy = None
            if xy is not None:
                self._run(["mousemove", "--sync", str(int(xy[0])), str(int(xy[1]))])
            for op in ops:
                self._run(op)

    def pointer(self, x, y, mask):
        with self._cond:
            self._latest_xy = (int(x), int(y))
            for btn, bit in ((1, 0x01), (2, 0x02), (3, 0x04)):
                pressed = bool(mask & bit)
                was = bool(self._prev_buttons & bit)
                if pressed and not was:
                    self._queue.append(["mousedown", str(btn)])
                elif was and not pressed:
                    self._queue.append(["mouseup", str(btn)])
            if (mask & 0x08) and not (self._prev_buttons & 0x08):
                self._queue.append(["click", "4"])
            if (mask & 0x10) and not (self._prev_buttons & 0x10):
                self._queue.append(["click", "5"])
            self._prev_buttons = mask
            self._cond.notify()

    def key(self, keysym, down):
        name = keysym_to_xdotool(keysym)
        if name is None:
            return
        with self._cond:
            self._queue.append([("keydown" if down else "keyup"), name])
            self._cond.notify()


# ---------------------------------------------------------------------------
# VNC Server（RFB 003.008）
# ---------------------------------------------------------------------------
_SILENT_ERRNOS = {errno.EBADF}
if os.name == "nt":
    # WSAENOTSOCK(10038) / WSAECONNABORTED(10053) / WSAECONNRESET(10054)
    _SILENT_ERRNOS.update({10038, 10053, 10054})


# ---------------------------------------------------------------------------
# 系统剪贴板读写（VNC ClientCutText / ServerCutText 使用）
# Windows 用 ctypes 调用 user32；Linux 用 xclip（无工具时读写返回空）
# ---------------------------------------------------------------------------
def _clipboard_env():
    """xclip 需要 X display：优先使用 --xdisplay，其次进程环境"""
    env = os.environ.copy()
    env.setdefault("DISPLAY", _clip_display or "")
    return env


def _clipboard_set(text):
    """写入系统剪贴板"""
    if IS_WINDOWS:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(0):
                return
            try:
                user32.EmptyClipboard()
                data = text.encode("utf-16-le") + b"\x00\x00"
                h = kernel32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE|GMEM_ZEROINIT
                if h:
                    p = kernel32.GlobalLock(h)
                    if p:
                        ctypes.memmove(p, data, len(data))
                        kernel32.GlobalUnlock(h)
                        user32.SetClipboardData(13, h)  # CF_UNICODETEXT
            finally:
                user32.CloseClipboard()
        except Exception:
            pass
        return
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"],
                             stdin=subprocess.PIPE, env=_clipboard_env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.stdin.write(text.encode("utf-8"))
        p.stdin.close()
    except Exception as exc:
        try:
            log(f"剪贴板写入失败: {exc!r}")
        except Exception:
            pass


def _clipboard_get():
    """读取系统剪贴板文本；不支持/无工具时返回 None"""
    if IS_WINDOWS:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(0):
                return None
            try:
                h = user32.GetClipboardData(13)  # CF_UNICODETEXT
                if not h:
                    return None
                p = kernel32.GlobalLock(h)
                try:
                    if not p:
                        return None
                    return ctypes.wstring_at(p)
                finally:
                    kernel32.GlobalUnlock(h)
            finally:
                user32.CloseClipboard()
        except Exception:
            return None
    try:
        out = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                             capture_output=True, timeout=3,
                             env=_clipboard_env())
        if out.returncode == 0:
            return out.stdout.decode("utf-8", "replace")
    except Exception:
        pass
    return None


class VNCServer:
    """纯 Python RFB 服务器，无密码（SecurityType None），支持 Raw 编码。"""

    def __init__(self, host, port, grabber, input_sink):
        self.host = host
        self.port = port
        self.grabber = grabber
        self.input_sink = input_sink
        self._clients = []
        self.clipboard = ""      # 服务端当前剪贴板文本
        self._clip_version = 0   # 剪贴板版本号（变化时通知各客户端）
        self._clip_lock = threading.Lock()

    def serve_forever(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        log(f"VNC Server 监听 {self.host}:{self.port}（无密码）")
        threading.Thread(target=self._clipboard_poll, daemon=True).start()
        while True:
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            client = VNCClient(conn, self, self.grabber, self.input_sink)
            self._clients.append(client)
            threading.Thread(target=self._run_client, args=(client,),
                             daemon=True).start()

    def _clipboard_poll(self):
        """轮询系统剪贴板，内容变化时更新内部剪贴板（推送见各客户端）"""
        while True:
            time.sleep(1.0)
            try:
                text = _clipboard_get()
            except Exception:
                text = None
            if text is None:
                continue
            with self._clip_lock:
                if text != self.clipboard:
                    self.clipboard = text
                    self._clip_version += 1

    def set_clipboard(self, text):
        """接收客户端 ClientCutText：更新内部剪贴板并写入系统剪贴板"""
        with self._clip_lock:
            changed = bool(text) and text != self.clipboard
            if changed:
                self.clipboard = text
                self._clip_version += 1
        if changed:
            _clipboard_set(text)
        else:
            # 内容相同：不重复写系统剪贴板，避免"再复制一份"回灌
            log("剪贴板内容未变化，跳过系统剪贴板写入")

    def _run_client(self, client):
        try:
            client.run()
        except ConnectionError:
            pass
        except OSError as exc:
            if (exc.errno not in _SILENT_ERRNOS
                    and not isinstance(exc, (ConnectionResetError,
                                             BrokenPipeError))):
                log(f"VNC 客户端错误: {exc}")
        except Exception as exc:
            log(f"VNC 客户端错误: {exc}")
        finally:
            try:
                client.close()
            except Exception:
                pass
            if client in self._clients:
                self._clients.remove(client)

    def disconnect_all(self):
        """断开全部活跃 VNC 客户端（网页端断开连接按钮）"""
        for client in list(self._clients):
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()

    @property
    def connected(self):
        return bool(self._clients)


class VNCClient:
    def __init__(self, conn, server, grabber, input_sink):
        self.conn = conn
        self.server = server
        self.grabber = grabber
        self.input_sink = input_sink
        self.prev_data = None
        self.pixel_size = 4
        self._buf = b""
        self._last_clip_version = server._clip_version
        self._zco = None  # 跨 rect/FBU 复用的 zlib 流式压缩器
        self._encs = set()  # 客户端支持的编码集合（SetEncodings）

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def _recv(self, n):
        while len(self._buf) < n:
            chunk = self.conn.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def _send(self, data):
        self.conn.sendall(data)

    def run(self):
        self._send(b"RFB 003.008\n")
        if self._recv(12) != b"RFB 003.008\n":
            raise ConnectionError("version mismatch")
        self._send(b"\x01\x01")
        if self._recv(1) != b"\x01":
            raise ConnectionError("security type rejected")
        self._send(b"\x00\x00\x00\x00")
        self._recv(1)
        img = self.grabber.grab()
        w, h = img.size
        name = b"BetterVNC"
        fmt = struct.pack("!BBBBHHHBBBxxx", 32, 24, 0, 1, 255, 255, 255,
                          16, 8, 0)
        self._send(struct.pack("!HH", w, h) + fmt +
                   struct.pack("!I", len(name)) + name)
        self.width, self.height = w, h
        log(f"VNC 客户端已连接，屏幕 {w}x{h}")
        while True:
            msg_type = self._recv(1)[0]
            if msg_type == 0:
                self._recv(3)
                fmt_bytes = self._recv(16)
                self._parse_pixel_format(fmt_bytes)
            elif msg_type == 2:
                self._recv(1)
                n = struct.unpack("!H", self._recv(2))[0]
                self._encs = {struct.unpack("!i", self._recv(4))[0]
                              for _ in range(n)}
            elif msg_type == 3:
                incremental = self._recv(1)[0]
                self._recv(8)
                self._send_update(incremental)
            elif msg_type == 4:
                down = self._recv(1)[0]
                keysym = struct.unpack("!I", self._recv(4))[0]
                self._recv(2)
                self.input_sink.key(keysym, down)
            elif msg_type == 5:
                mask = self._recv(1)[0]
                x, y = struct.unpack("!HH", self._recv(4))
                while len(self._buf) >= 6 and self._buf[0] == 5:
                    nmask = self._buf[1]
                    if nmask != mask:
                        break
                    x, y = struct.unpack("!HH", self._buf[2:6])
                    self._buf = self._buf[6:]
                self.input_sink.pointer(x, y, mask)
            elif msg_type == 6:
                self._recv(3)
                n = struct.unpack("!I", self._recv(4))[0]
                raw = self._recv(n)
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    text = raw.decode("latin-1", "replace")
                if text:
                    log(f"收到剪贴板文本 {len(text)} 字符")
                    self.server.set_clipboard(text)
            else:
                log(f"VNC 客户端未知消息类型: {msg_type}")
                break

    def _parse_pixel_format(self, fmt):
        (bpp, depth, big, true_colour, rmax, gmax, bmax,
         rshift, gshift, bshift) = struct.unpack("!BBBBHHHBBB", fmt[:13])
        self.pixel_size = max(1, bpp // 8)
        self.client_fmt = (bpp, big, true_colour, rshift, gshift, bshift)

    def _pixels(self, img):
        """把 RGB 图像转换为客户端像素格式（默认 32bpp 小端 BGRX）。"""
        fmt = getattr(self, "client_fmt", None)
        bpp, big, true_colour, rshift, gshift, bshift = (
            fmt if fmt else (32, 0, 1, 16, 8, 0))
        if bpp >= 24 and true_colour and not big:
            if (rshift, gshift, bshift) == (16, 8, 0):
                return img.tobytes("raw", "BGRX")
            if (rshift, gshift, bshift) == (0, 8, 16):
                return img.tobytes("raw", "RGBX")
        rgb = img.tobytes()
        if bpp >= 16:
            bytes_per = 2
            rshift2 = rshift % 16
            gshift2 = gshift % 16
            bshift2 = bshift % 16
            rmax = ((255 << rshift2) & 0xFFFF) >> rshift2
            gmax = ((255 << gshift2) & 0xFFFF) >> gshift2
            bmax = ((255 << bshift2) & 0xFFFF) >> bshift2
        elif bpp >= 8:
            bytes_per = 1
        else:
            bytes_per = 1
        px = bytearray(len(rgb) // 3 * bytes_per)
        out = 0
        for i in range(0, len(rgb), 3):
            r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
            if bpp >= 16:
                r5 = (r >> (8 - ((rmax.bit_length())))) if rmax < 256 else r
                g6 = (g >> (8 - ((gmax.bit_length())))) if gmax < 256 else g
                b5 = (b >> (8 - ((bmax.bit_length())))) if bmax < 256 else b
                v = (r5 << rshift2) | (g6 << gshift2) | (b5 << bshift2)
                px[out:out + bytes_per] = v.to_bytes(bytes_per, "big" if big else "little")
            else:
                px[out] = r
            out += bytes_per
        return bytes(px)

    def _send_update(self, incremental):
        srv = self.server
        with srv._clip_lock:
            if self._last_clip_version != srv._clip_version:
                self._last_clip_version = srv._clip_version
                clip = srv.clipboard
            else:
                clip = None
        if clip is not None:
            data = clip.encode("utf-8")
            self._send(b"\x03\x00\x00\x00" + struct.pack("!I", len(data)) + data)
        img = self.grabber.grab()
        w, h = img.size
        if w != self.width or h != self.height:
            self.width, self.height = w, h
            incremental = 0
        data = self._pixels(img)
        if incremental and self.prev_data is not None:
            rects = self._diff(self.prev_data, data, w, h)
            if not rects:
                self._send(struct.pack("!BBH", 0, 0, 0))
                return
        else:
            rects = [(0, 0, w, h)]
        self.prev_data = data
        self._send_fbu(data, w, h, rects)

    def _diff(self, prev, cur, w, h):
        stride = self.pixel_size
        row_bytes = w * stride
        block = 64
        rects = []
        for by in range(0, h, block):
            rh = min(block, h - by)
            for bx in range(0, w, block):
                rw = min(block, w - bx)
                changed = False
                for y in range(by, by + rh):
                    o0 = y * row_bytes + bx * stride
                    o1 = o0 + rw * stride
                    if prev[o0:o1] != cur[o0:o1]:
                        changed = True
                        break
                if changed:
                    rects.append((bx, by, rw, rh))
        if len(rects) > 128:
            return [(0, 0, w, h)]
        return rects

    def _send_fbu(self, data, w, h, rects):
        import zlib
        out = bytearray(struct.pack("!BBH", 0, 0, len(rects)))
        row_bytes = w * self.pixel_size
        enc_choice = load_encoder()
        encs = getattr(self, "_encs", set())
        for (x, y, rw, rh) in rects:
            if enc_choice == "hextile" and 5 in encs:
                out += struct.pack("!HHHH", x, y, rw, rh)
                out += struct.pack("!i", 5)  # HEXTILE
                out += self._encode_hextile(data, w, x, y, rw, rh, row_bytes)
            elif enc_choice == "zlib" and 6 in encs:
                raw = bytearray()
                for yy in range(y, y + rh):
                    off = yy * row_bytes + x * self.pixel_size
                    raw += data[off:off + rw * self.pixel_size]
                if self._zco is None:
                    self._zco = zlib.compressobj(6)
                body = self._zco.compress(bytes(raw))
                body += self._zco.flush(zlib.Z_SYNC_FLUSH)
                out += struct.pack("!HHHH", x, y, rw, rh)
                out += struct.pack("!i", 6)  # ZLIB
                out += struct.pack("!I", len(body))
                out += body
            else:
                out += struct.pack("!HHHHI", x, y, rw, rh, 0)
                for yy in range(y, y + rh):
                    off = yy * row_bytes + x * self.pixel_size
                    out += data[off:off + rw * self.pixel_size]
        self._send(bytes(out))

    def _encode_hextile(self, data, w, x, y, rw, rh, row_bytes):
        """Hextile 编码：16x16 块，每块子编码 Raw(0x01)"""
        ps = self.pixel_size
        out = bytearray()
        for by in range(y, y + rh, 16):
            bh = min(16, y + rh - by)
            for bx in range(x, x + rw, 16):
                bw = min(16, x + rw - bx)
                out.append(0x01)  # 子编码 Raw
                for yy in range(by, by + bh):
                    off = yy * row_bytes + bx * ps
                    out += data[off:off + bw * ps]
        return out


# ---------------------------------------------------------------------------
# 文件管理 API
# ---------------------------------------------------------------------------
def _normalize(path):
    if not path:
        return os.getcwd()
    return os.path.normpath(path)


def _is_windows_root(path):
    return len(path) <= 3 and path[1:3] == ":\\"


def list_drives():
    if not IS_WINDOWS:
        return ["/"]
    drives = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    letter = ord("A")
    while mask:
        if mask & 1:
            drives.append(f"{chr(letter)}:/")
        mask >>= 1
        letter += 1
    return drives


def fs_list(path):
    path = _normalize(path)
    items = []
    if _is_windows_root(path) and path[0].isalpha() and path[2] == "\\":
        pass
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as exc:
        return {"error": str(exc)}
    for e in entries:
        try:
            st = e.stat()
            items.append({
                "name": e.name,
                "is_dir": e.is_dir(),
                "size": st.st_size if not e.is_dir() else 0,
                "mtime": int(st.st_mtime),
            })
        except OSError:
            continue
    parent = os.path.dirname(path.rstrip("\\/")) if path not in list_drives() else None
    return {"path": path, "parent": parent, "items": items}


def fs_download(path):
    path = _normalize(path)
    if not os.path.isfile(path):
        return None
    return path


def fs_zip(paths, dst):
    """把多个路径打包为 zip 写入 dst 文件句柄。返回文件条目数。"""
    count = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            p = _normalize(p)
            if not os.path.exists(p):
                continue
            if os.path.isdir(p):
                base = os.path.basename(p.rstrip("\\/")) or "folder"
                for root, dirs, files in os.walk(p):
                    for f in files:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, p)
                        arc = os.path.join(base, rel).replace(os.sep, "/")
                        zf.write(full, arc)
                        count += 1
            else:
                zf.write(p, os.path.basename(p))
                count += 1
    return count


def parse_multipart(body, boundary):
    """解析 multipart/form-data，返回 (fields, files)。"""
    fields = {}
    files = []
    delimiter = b"--" + boundary.encode()
    parts = body.split(delimiter)
    for part in parts:
        if part in (b"", b"--", b"--\r\n", b"\r\n"):
            continue
        part = part.lstrip(b"\r\n")
        head, _, content = part.partition(b"\r\n\r\n")
        content = content.rstrip(b"\r\n")
        name = None
        filename = None
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-disposition:"):
                for kv in line.decode("latin-1").split(";"):
                    kv = kv.strip()
                    if kv.lower().startswith("name="):
                        name = kv[5:].strip('"')
                    elif kv.lower().startswith("filename*="):
                        val = kv.split("=", 1)[1].strip().strip('"')
                        if "'" in val:
                            charset, _lang, pct = val.split("'", 2)
                            try:
                                from urllib.parse import unquote
                                filename = unquote(pct, encoding=charset)
                            except Exception:
                                filename = pct
                        else:
                            filename = val
                    elif kv.lower().startswith("filename="):
                        raw_val = kv[9:].strip('"')
                        try:
                            filename = raw_val.encode("latin-1").decode("utf-8")
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            filename = raw_val
        if filename is not None:
            files.append({"name": name, "filename": filename, "content": content})
        elif name is not None:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


def run_command(command, timeout=300):
    """同步执行（GUI 等内部使用）；网页端使用下方的作业系统"""
    if not command:
        return {"exit_code": 0, "output": ""}
    if IS_WINDOWS:
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", command]
    else:
        cmd = ["/bin/sh", "-c", command]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": "[timeout]" }
    except Exception as exc:
        return {"exit_code": -1, "output": str(exc)}
    raw = proc.stdout + proc.stderr
    return {"exit_code": proc.returncode, "output": decode_output(raw)}


def decode_output(raw):
    """命令输出解码：优先 UTF-8，失败依次尝试 GBK 等本地编码"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in ("gbk", "cp437"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# 命令作业系统：网页端提交命令立即返回作业号，前端轮询获取增量输出，
# 避免 GUI/交互/长命令导致 HTTP 连接挂起（Failed to fetch）
# ---------------------------------------------------------------------------
_cmd_jobs = {}
_cmd_jobs_lock = threading.Lock()
_CMD_JOB_LIMIT = 30
_CMD_JOB_TTL = 600


class CmdJob:
    def __init__(self, command, timeout):
        import secrets
        self.id = secrets.token_hex(8)
        self.command = command
        self.timeout = timeout
        self.raw = bytearray()
        self.text_len = 0
        self.done = False
        self.exit_code = None
        self.started = time.time()
        self.finished = 0
        self.proc = None
        self.killed = False

    def text(self):
        return decode_output(bytes(self.raw))


def _cleanup_jobs():
    now = time.time()
    with _cmd_jobs_lock:
        stale = [jid for jid, j in _cmd_jobs.items()
                 if j.done and now - j.finished > _CMD_JOB_TTL]
        for jid in stale:
            _cmd_jobs.pop(jid, None)
        while len(_cmd_jobs) > _CMD_JOB_LIMIT:
            for jid in sorted(_cmd_jobs, key=lambda k: _cmd_jobs[k].started):
                if _cmd_jobs[jid].done:
                    _cmd_jobs.pop(jid, None)
                    break
            else:
                break


def start_cmd_job(command, timeout=300):
    if not command:
        return None
    if IS_WINDOWS:
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", command]
    else:
        cmd = ["/bin/sh", "-c", command]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    except Exception as exc:
        job = CmdJob(command, timeout)
        job.done = True
        job.exit_code = -1
        job.finished = time.time()
        job.raw.extend(str(exc).encode("utf-8", "replace"))
        return job

    job = CmdJob(command, timeout)
    job.proc = proc
    with _cmd_jobs_lock:
        _cmd_jobs[job.id] = job
    _cleanup_jobs()

    def reader():
        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                job.raw.extend(chunk)
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            job.exit_code = proc.wait()
            job.done = True
            job.finished = time.time()

    def watchdog():
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_job(job.id)
        if timed_out or job.killed:
            job.raw.extend(
                "\n[webvnc] 命令已终止（超时或手动停止）\n".encode("utf-8"))

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    return job


def kill_job(job_id):
    with _cmd_jobs_lock:
        job = _cmd_jobs.get(job_id)
    if not job or not job.proc or job.done:
        return False
    job.killed = True
    try:
        if IS_WINDOWS:
            # 连同子进程树一起终止
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(job.proc.pid)],
                capture_output=True, creationflags=NO_WINDOW)
        else:
            job.proc.terminate()
    except Exception:
        try:
            job.proc.kill()
        except Exception:
            pass
    return True


def system_info():
    info = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cwd": os.getcwd(),
        "drives": list_drives(),
        "windows": IS_WINDOWS,
        "vnc_virtual": (not IS_WINDOWS) or (Image is None),
    }
    if IS_WINDOWS:
        info["hostname"] = os.environ.get("COMPUTERNAME", "")
    else:
        info["hostname"] = socket.gethostname()
    return info


# ---------------------------------------------------------------------------
# HTTPS + WebSocket 处理器
# ---------------------------------------------------------------------------
class WebHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30  # 空闲 keep-alive 连接 30 秒自动关闭，防止挂起连接堆积句柄
    server_version = "BetterVNC/1.0"
    directory = "web"  # 相对路径，main() 已切换到脚本目录
    vnc_host = "127.0.0.1"
    vnc_port = 5900
    token = None
    vnc_server = None

    # ---- 辅助 ----
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_token(self):
        if not self.token:
            return True
        return self.headers.get("X-Token") == self.token

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    # ---- 路由 ----
    def do_GET(self):
        if self.headers.get("Upgrade", "").lower() == "websocket":
            return self._handle_websocket()
        path = self.path.split("?")[0]
        if path == "/api/info":
            return self._send_json(system_info())
        if path == "/api/fs/drives":
            return self._send_json({"drives": list_drives()})
        if path == "/api/fs/list":
            return self._fs_list()
        if path == "/api/fs/download":
            return self._fs_download()
        if path == "/api/fs/zip":
            return self._fs_zip()
        if path == "/api/cmd":
            return self._send_json({"error": "use POST"}, 405)
        if path == "/api/cmd/result":
            return self._api_cmd_result()
        if path == "/api/log/tail":
            return self._api_log_tail()
        if path == "/api/netstat":
            return self._send_json({"ports": get_netstat()})
        if path == "/api/ping":
            return self._send_json({"pong": True})
        if path == "/api/system":
            return self._send_json(get_system_stats())
        if path == "/api/clipboard":
            srv = WebHandler.vnc_server
            text = ""
            if srv:
                with srv._clip_lock:
                    text = srv.clipboard
            if not text:
                try:
                    text = _clipboard_get() or ""
                except Exception:
                    text = ""
            return self._send_json({"text": text})
        if path == "/api/theme":
            return self._send_json({"theme": load_theme()})
        if path == "/api/encoder":
            return self._send_json({"encoder": load_encoder(),
                                    "encoders": list(_ENCODERS)})
        if path == "/api/vnc/status":
            srv = WebHandler.vnc_server
            return self._send_json({
                "connected": bool(srv and srv.connected),
                "clients": len(srv._clients) if srv else 0,
            })
        if path == "/api/vnc/disconnect":
            srv = WebHandler.vnc_server
            if srv:
                srv.disconnect_all()
            return self._send_json({"ok": True})
        if path in ("/", ""):
            return self._serve_index()
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        self._serve_static()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/cmd":
            return self._api_cmd()
        if path == "/api/cmd/kill":
            return self._api_cmd_kill()
        if path == "/api/fs/upload":
            return self._fs_upload()
        if path == "/api/fs/mkdir":
            return self._fs_mkdir()
        if path == "/api/fs/rename":
            return self._fs_rename()
        if path == "/api/fs/move":
            return self._fs_move()
        if path == "/api/fs/delete":
            return self._fs_delete()
        if path == "/api/theme":
            try:
                body = self._read_body() or b"{}"
                data = json.loads(body)
                theme = data.get("theme", "dark")
                save_theme(theme)
                return self._send_json({"theme": theme, "saved": True})
            except (ValueError, OSError) as exc:
                return self._send_json({"error": str(exc)}, 500)
        if path == "/api/encoder":
            try:
                body = self._read_body() or b"{}"
                data = json.loads(body)
                encoder = data.get("encoder", "zlib")
                save_encoder(encoder)
                return self._send_json({"encoder": encoder, "saved": True})
            except (ValueError, OSError) as exc:
                return self._send_json({"error": str(exc)}, 500)
        if path == "/api/log/new":
            try:
                with _log_lock:
                    fname = _new_log_file()
                return self._send_json({"file": os.path.basename(fname)})
            except OSError as exc:
                return self._send_json({"error": str(exc)}, 500)
        if path == "/api/clipboard":
            try:
                body = self._read_body() or b"{}"
                data = json.loads(body)
                text = data.get("text", "")
                srv = WebHandler.vnc_server
                if srv:
                    srv.set_clipboard(text)
                else:
                    _clipboard_set(text)
                return self._send_json({"text": text, "saved": True})
            except (ValueError, OSError) as exc:
                return self._send_json({"error": str(exc)}, 500)
        if path == "/api/vnc/disconnect":
            srv = WebHandler.vnc_server
            if srv:
                srv.disconnect_all()
            return self._send_json({"ok": True})
        if path == "/api/power":
            try:
                body = self._read_body() or b"{}"
                data = json.loads(body)
                action = data.get("action", "")
                if action not in ("shutdown", "reboot", "restart_service"):
                    return self._send_json({"error": "invalid action"}, 400)
                if action in ("shutdown", "reboot"):
                    log(f"远程电源操作: {action}")
                ok = power_action(action)
                return self._send_json({"ok": ok, "action": action})
            except (ValueError, OSError) as exc:
                return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"error": "not found"}, 404)

    # ---- 动态注入 vnc.html ----
    # 访问根路径或 /vnc.html 时返回注入服务端配置后的调整页面，
    # 保证打开即自动连接（无需手动填写 host/port/path）。
    _index_cache = None  # (mtime_ns, size, body)

    def _serve_index(self):
        path = os.path.join(self.directory, "vnc.html")
        try:
            st = os.stat(path)
        except OSError:
            self.send_error(404)
            return
        cached = WebHandler._index_cache
        if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
            body = cached[2]
        else:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
            cfg = {
                "path": "websockify",
                "encrypt": isinstance(self.connection, ssl.SSLSocket),
                "vnc_host": self.vnc_host,
                "vnc_port": self.vnc_port,
                "machine": socket.gethostname(),
                "platform": sys.platform,
                "windows": IS_WINDOWS,
                "virtual": (not IS_WINDOWS) or (Image is None),
                "auth": bool(self.token),
            }
            inject = "<script>window.__WEBVNC__ = %s;</script>" % json.dumps(
                cfg, ensure_ascii=False)
            if "</head>" in html:
                html = html.replace("</head>", inject + "\n</head>", 1)
            else:
                html += inject
            body = html.encode("utf-8")
            WebHandler._index_cache = (st.st_mtime_ns, st.st_size, body)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- 静态文件 ----
    def _serve_static(self):
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        rel = urllib.parse.unquote(parsed.path).lstrip("/")
        full = os.path.normpath(os.path.join(self.directory, rel))
        if not full.startswith(self.directory):
            return self._send_json({"error": "forbidden"}, 403)
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            self.send_error(404)
            return
        if rel == "vnc.html":
            return self._serve_index()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        size = os.path.getsize(full)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with open(full, "rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    # ---- 文件管理 ----
    def _get_query(self, key, default=None):
        import urllib.parse
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        val = q.get(key)
        return val[0] if val else default

    def _fs_list(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        path = self._get_query("path", None)
        return self._send_json(fs_list(path or ""))

    def _fs_download(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        import urllib.parse
        path = self._get_query("path", None)
        if not path:
            return self._send_json({"error": "missing path"}, 400)
        full = _normalize(path)
        if not os.path.isfile(full):
            return self._send_json({"error": "file not found"}, 404)
        size = os.path.getsize(full)
        name = os.path.basename(full)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition",
                         f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}")
        self.end_headers()
        with open(full, "rb") as fh:
            shutil.copyfileobj(fh, self.wfile)

    def _fs_zip(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        raw = self._get_query("paths", None)
        if not raw:
            return self._send_json({"error": "missing paths"}, 400)
        import urllib.parse
        paths = [urllib.parse.unquote(p) for p in raw.split(",")]
        tmp = tempfile.NamedTemporaryFile(prefix="webvnc_zip_", suffix=".zip",
                                          delete=False)
        tmp.close()
        try:
            with open(tmp.name, "wb") as fh:
                fs_zip(paths, fh)
            size = os.path.getsize(tmp.name)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", "attachment; filename=webvnc.zip")
            self.end_headers()
            with open(tmp.name, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def _fs_upload(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        dest = self._get_query("path", None)
        ctype = self.headers.get("Content-Type", "")
        if "boundary=" not in ctype:
            return self._send_json({"error": "bad multipart"}, 400)
        boundary = ctype.split("boundary=")[1].strip().strip('"')
        body = self._read_body()
        if not dest:
            return self._send_json({"error": "missing path"}, 400)
        dest = _normalize(dest)
        if not os.path.isdir(dest):
            return self._send_json({"error": "target not a directory"}, 400)
        _, files = parse_multipart(body, boundary)
        saved = []
        for f in files:
            target = os.path.join(dest, os.path.basename(f["filename"]))
            with open(target, "wb") as fh:
                fh.write(f["content"])
            saved.append(f["filename"])
        return self._send_json({"saved": saved})

    def _fs_mkdir(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        data = json.loads(self._read_body() or b"{}")
        path = data.get("path", "")
        if not path:
            return self._send_json({"error": "missing path"}, 400)
        try:
            os.makedirs(_normalize(path), exist_ok=True)
            return self._send_json({"ok": True})
        except OSError as exc:
            return self._send_json({"error": str(exc)}, 500)

    def _fs_rename(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        data = json.loads(self._read_body() or b"{}")
        path, new_name = data.get("path", ""), data.get("new_name", "")
        if not path or not new_name:
            return self._send_json({"error": "missing path/new_name"}, 400)
        full = _normalize(path)
        new_path = os.path.join(os.path.dirname(full), new_name)
        try:
            os.rename(full, new_path)
            return self._send_json({"ok": True, "path": new_path})
        except OSError as exc:
            return self._send_json({"error": str(exc)}, 500)

    def _fs_move(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        data = json.loads(self._read_body() or b"{}")
        paths = data.get("paths", [])
        dest = data.get("dest", "")
        if not paths or not dest:
            return self._send_json({"error": "missing paths/dest"}, 400)
        dest = _normalize(dest)
        moved = []
        for p in paths:
            src = _normalize(p)
            try:
                shutil.move(src, os.path.join(dest, os.path.basename(src)))
                moved.append(p)
            except OSError as exc:
                return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"ok": True, "moved": moved})

    def _fs_delete(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        try:
            data = json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "bad json"}, 400)
        paths = data.get("paths", [])
        if not paths:
            return self._send_json({"error": "missing paths"}, 400)
        deleted = []
        for p in paths:
            full = _normalize(p)
            if not os.path.exists(full):
                continue
            try:
                if os.path.isdir(full) and not os.path.islink(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                deleted.append(p)
            except OSError as exc:
                return self._send_json(
                    {"error": str(exc), "deleted": deleted}, 500)
        return self._send_json({"ok": True, "deleted": deleted})

    # ---- 命令执行（作业 + 轮询，避免长命令挂起连接） ----
    def _api_cmd(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        try:
            data = json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "bad json"}, 400)
        command = data.get("command", "")
        timeout = int(data.get("timeout", 300))
        if not command:
            return self._send_json({"error": "missing command"}, 400)
        job = start_cmd_job(command, timeout)
        if job is None:
            return self._send_json({"error": "empty command"}, 400)
        return self._send_json({"job": job.id})

    def _api_cmd_result(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        job_id = self._get_query("id", "")
        try:
            seq = int(self._get_query("seq", "0"))
        except ValueError:
            seq = 0
        with _cmd_jobs_lock:
            job = _cmd_jobs.get(job_id)
        if not job:
            return self._send_json({"error": "job not found"}, 404)
        text = job.text()
        return self._send_json({
            "output": text[seq:],
            "total": len(text),
            "done": job.done,
            "exit_code": job.exit_code,
        })

    def _api_cmd_kill(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        try:
            data = json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "bad json"}, 400)
        job_id = data.get("id", "")
        with _cmd_jobs_lock:
            job = _cmd_jobs.get(job_id)
        if not job:
            return self._send_json({"error": "job not found"}, 404)
        kill_job(job_id)
        return self._send_json({"ok": True})

    # ---- 服务端日志 ----
    def _api_log_tail(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        try:
            start = int(self._get_query("start", "-1"))
        except ValueError:
            start = -1
        try:
            lines = int(self._get_query("lines", "300"))
        except ValueError:
            lines = 300
        lines = max(1, min(lines, 2000))
        try:
            names = sorted(
                n for n in os.listdir(LOG_DIR)
                if n.startswith("webvnc_") and n.endswith(".log"))
        except OSError:
            names = []
        if not names:
            return self._send_json({"file": "", "start": 0, "next": 0, "lines": []})
        newest = names[-1]
        try:
            with open(os.path.join(LOG_DIR, newest), "r",
                      encoding="utf-8", errors="replace") as fh:
                all_lines = fh.readlines()
        except OSError:
            all_lines = []
        if start < 0:
            idx0 = max(0, len(all_lines) - lines)
        else:
            idx0 = min(start, len(all_lines))
        tail = all_lines[idx0:]
        return self._send_json({
            "file": newest,
            "start": idx0,
            "next": len(all_lines),
            "lines": [l.rstrip("\r\n") for l in tail],
        })

    # ---- WebSocket 代理 ----
    def _handle_websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400)
            return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response_only(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        try:
            vnc = socket.create_connection((self.vnc_host, self.vnc_port),
                                           timeout=10)
        except OSError as exc:
            log(f"无法连接内置 VNC Server: {exc}")
            try:
                send_frame(self.connection, 0x8, b"\x03\xea")
            except Exception:
                pass
            self.close_connection = True
            return
        vnc.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        done = threading.Event()

        def vnc_to_ws():
            try:
                while not done.is_set():
                    data = vnc.recv(MAX_FRAME)
                    if not data:
                        break
                    send_frame(self.connection, 0x2, data)
            except Exception:
                pass
            finally:
                done.set()

        threading.Thread(target=vnc_to_ws, daemon=True).start()
        try:
            while not done.is_set():
                opcode, payload = recv_frame(self.connection)
                if opcode in (0x1, 0x2, 0x0):
                    vnc.sendall(payload)
                elif opcode == 0x8:
                    try:
                        send_frame(self.connection, 0x8, payload[:2])
                    except Exception:
                        pass
                    break
                elif opcode == 0x9:
                    try:
                        send_frame(self.connection, 0xA, payload)
                    except Exception:
                        pass
            done.set()
        except (WebSocketError, ConnectionError, OSError):
            pass
        finally:
            done.set()
            try:
                vnc.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            vnc.close()
        self.close_connection = True

    def log_message(self, fmt, *args):
        pass


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def ensure_cert_files(cert_path, key_path):
    changed = False
    if not os.path.isfile(cert_path):
        with open(cert_path, "w") as fh:
            fh.write(_TLS_CERT)
        changed = True
    if not os.path.isfile(key_path):
        with open(key_path, "w") as fh:
            fh.write(_TLS_KEY)
        changed = True
    if changed:
        log(f"已生成自签名证书 {cert_path}")


def main():
    global _clip_display
    # Windows 控制台默认 GBK，强制 UTF-8 输出避免中文日志乱码
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

    log(f"========== BetterVNC 启动 ==========")
    log(f"程序目录: {BASE}")
    log(f"Python: {sys.executable} (v{sys.version.split()[0]})")
    if IS_WINDOWS:
        log(f"系统: Windows {platform.version()}")
    else:
        log(f"系统: {os.name} / {platform.system()}")

    ap = argparse.ArgumentParser(
        description="BetterVNC - Windows 远程管理工具（VNC + HTTPS 文件管理 + 终端）")
    ap.add_argument("--host", default="0.0.0.0", help="Web 监听地址（默认 0.0.0.0）")
    ap.add_argument("--port", type=int, default=6080, help="HTTPS 端口（默认 6080）")
    ap.add_argument("--vnc-host", default="0.0.0.0", help="VNC Server 监听地址")
    ap.add_argument("--vnc-port", type=int, default=5900, help="VNC 端口（默认 5900）")
    ap.add_argument("--token", default="", help="访问令牌（可选，保护 API）")
    ap.add_argument("--no-https", action="store_true", help="使用 HTTP 而非 HTTPS")
    ap.add_argument("--xdisplay", default="",
                    help="Linux 虚拟桌面 X display（如 :99），抓取真实 X 桌面并模拟输入")
    args = ap.parse_args()
    global _main_args
    _main_args = args

    # 一律使用相对路径：先切换到脚本所在目录
    os.chdir(BASE)

    # 每次启动创建新的时间戳日志文件，并清理前一天日志
    with _log_lock:
        _new_log_file()
        _clean_old_logs()

    # 依赖自检：缺少 Pillow 时自动安装并重启进程
    ensure_dependencies()

    if not IS_WINDOWS:
        if args.xdisplay:
            log(f"Linux 虚拟桌面模式：抓取 X display {args.xdisplay}（键鼠输入可用）")
        else:
            log("非 Windows 平台：启用虚拟屏幕演示模式（键鼠输入不可用）")

    grabber = ScreenGrabber(args.xdisplay or None)
    if args.xdisplay:
        _clip_display = args.xdisplay
    elif not IS_WINDOWS:
        _clip_display = os.environ.get("DISPLAY")
    if IS_WINDOWS:
        input_sink = WindowsInput()
    elif args.xdisplay:
        input_sink = XInput(args.xdisplay)
    else:
        input_sink = NullInput()

    vnc_srv = VNCServer(args.vnc_host, args.vnc_port, grabber, input_sink)
    WebHandler.vnc_server = vnc_srv
    vnc_thread = threading.Thread(target=vnc_srv.serve_forever, daemon=True)
    vnc_thread.start()
    time.sleep(0.3)

    WebHandler.vnc_host = "127.0.0.1"
    WebHandler.vnc_port = args.vnc_port
    WebHandler.token = args.token or None

    httpd = ThreadingHTTPServer((args.host, args.port), WebHandler)
    if not args.no_https:
        cert_path = "cert.pem"
        key_path = "key.pem"
        ensure_cert_files(cert_path, key_path)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_path, key_path)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http"

    log(f"Web 服务已启动: {scheme}://{args.host}:{args.port}/vnc.html")
    log(f"文件管理/终端 API 前缀: {scheme}://{args.host}:{args.port}/api/")
    if args.token:
        log("已启用访问令牌保护")
    else:
        log("警告: 未启用访问令牌，服务对外开放请务必设置 --token 并注意安全")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("服务已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
