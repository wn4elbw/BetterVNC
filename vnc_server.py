#!/usr/bin/env python3
"""
vnc_server.py
跨平台 (Windows / Linux) 的 noVNC Web 服务端：运行后把本机屏幕开放到端口。

功能：
  - 提供 noVNC 静态页面 (vnc.html / vnc_lite.html 等)，打开即自动连接（无点击连接）
  - 在 /websockify 端点提供 WebSocket 代理，把浏览器的 WebSocket 转发到 VNC 服务器
  - 自动将本机屏幕共享为 VNC（Linux 优先用 x11vnc 共享真实屏幕，无真实屏幕时
    回退 TigerVNC Xvnc 虚拟桌面；Windows 使用已安装的 VNC Server）
  - 全部无密码（x11vnc -nopw / Xvnc -SecurityTypes None）
  - 将服务开放到指定端口（默认 6080），浏览器访问即可看到本机屏幕

依赖：仅 Python 3 标准库，无需第三方包。
     共享本机屏幕需要 x11vnc（Linux）或已安装的 VNC Server（Windows）。

用法：
  python3 vnc_server.py                          # 默认 0.0.0.0:6080，本机屏幕 -> 5900
  python3 vnc_server.py --port 6080 --display :0 # 指定共享显示 :0
  python3 vnc_server.py --vnc-host 192.168.1.10 --vnc-port 5900  # 代理远程 VNC
  python3 vnc_server.py --no-auto-vnc            # 不自动启动本机 VNC
"""

import argparse
import base64
import hashlib
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 65536


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
    """读取一个 WebSocket 帧（客户端 -> 服务端，带掩码）。"""
    b0, b1 = recv_exact(sock, 2)
    fin = (b0 >> 7) & 0x01
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
    return fin, opcode, payload


def send_frame(sock, opcode, payload=b"", fin=True):
    """发送一个 WebSocket 帧（服务端 -> 客户端，无掩码）。"""
    header = bytearray([(0x80 if fin else 0x00) | opcode])
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


def port_open(host, port, timeout=1):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def detect_display():
    """检测本机可用的 X 显示（真实屏幕）。"""
    display = os.environ.get("DISPLAY")
    if display:
        return display
    if os.name != "nt" and os.path.isdir("/tmp/.X11-unix"):
        try:
            names = sorted(os.listdir("/tmp/.X11-unix"))
        except OSError:
            names = []
        for name in names:
            if name.startswith("X"):
                return ":" + name[1:]
    return None


def wait_for_port(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(0.5)
    return False


def start_x11vnc(vnc_port, display):
    """用 x11vnc 共享本机真实屏幕，无密码 (-nopw)。"""
    x11vnc = shutil.which("x11vnc")
    if x11vnc is None:
        return None
    cmd = [x11vnc, "-display", display,
           "-nopw", "-forever", "-shared", "-many",
           "-rfbport", str(vnc_port), "-localhost", "no", "-bg"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"[warn] 启动 x11vnc 失败: {exc}")
        return None
    if wait_for_port("127.0.0.1", vnc_port):
        print(f"[info] 已共享本机屏幕 (x11vnc, 显示 {display})，端口 {vnc_port}（无密码）")
        return proc
    print("[warn] x11vnc 未能在端口上监听，尝试回退到虚拟桌面")
    return None


def start_xvnc(vnc_port):
    """无真实屏幕时回退：启动 TigerVNC Xvnc 虚拟桌面，无密码。"""
    xvnc = shutil.which("Xvnc")
    if xvnc is None:
        return None
    proc = None
    for display_num in (1, 2, 3, 99):
        display = f":{display_num}"
        cmd = [xvnc, display, "-geometry", "1280x800", "-depth", "24",
               "-SecurityTypes", "None", "-localhost", "no",
               "-rfbport", str(vnc_port), "-ac", "-nolisten", "tcp"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError as exc:
            print(f"[warn] 启动 Xvnc 失败: {exc}")
            return None
        if wait_for_port("127.0.0.1", vnc_port):
            print(f"[info] 已启动虚拟桌面 (Xvnc {display})，端口 {vnc_port}（无密码）")
            return proc
        try:
            proc.terminate()
        except Exception:
            pass
        proc = None
    print("[warn] Xvnc 启动失败")
    return None


def ensure_local_vnc(vnc_host, vnc_port, display=None):
    """按需启动本机 VNC 服务，将本机屏幕开放到端口（无密码）。"""
    if vnc_host not in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        print(f"[info] VNC 目标为远程地址 {vnc_host}:{vnc_port}，跳过本地 VNC 检测")
        return None
    if port_open("127.0.0.1", vnc_port):
        print(f"[info] 检测到本机已有 VNC 服务监听端口 {vnc_port}")
        return None

    if os.name == "nt":
        print("[warn] 未检测到本机 VNC 服务。")
        print("       Windows 请安装并运行 TightVNC/UltraVNC Server 后重试，")
        print(f"       或使用 --vnc-host/--vnc-port 指向远程 VNC 服务器。")
        return None

    if display is None:
        display = detect_display()

    if display:
        proc = start_x11vnc(vnc_port, display)
        if proc is not None:
            return proc
        print(f"[info] 无法共享显示 {display}，回退到虚拟桌面")

    proc = start_xvnc(vnc_port)
    if proc is not None:
        return proc

    print("[warn] 未能启动本机 VNC 服务，请检查依赖 (x11vnc / tigervnc)")
    return None


class ProxyConnection:
    """单个 WebSocket <-> VNC TCP 双向转发连接。"""

    def __init__(self, ws_sock, vnc_host, vnc_port):
        self.ws = ws_sock
        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self._send_lock = threading.Lock()
        self._closed = threading.Event()

    def run(self):
        try:
            tcp = socket.create_connection((self.vnc_host, self.vnc_port), timeout=10)
        except OSError as exc:
            print(f"[error] 无法连接 VNC 服务器 {self.vnc_host}:{self.vnc_port}: {exc}")
            try:
                with self._send_lock:
                    send_frame(self.ws, 0x8, b"\x03\xea")
            except Exception:
                pass
            try:
                self.ws.close()
            except Exception:
                pass
            return

        tcp.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=self._vnc_to_ws, args=(tcp,), daemon=True).start()
        try:
            self._ws_to_vnc(tcp)
        except WebSocketError:
            pass
        except Exception as exc:
            print(f"[error] WebSocket 转发异常: {exc}")
        finally:
            self._closed.set()
            try:
                tcp.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            tcp.close()
            try:
                self.ws.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.ws.close()
            except Exception:
                pass

    def _ws_to_vnc(self, tcp):
        fragment = b""
        while not self._closed.is_set():
            fin, opcode, payload = recv_frame(self.ws)
            if opcode in (0x1, 0x2, 0x0):
                fragment += payload
                if fin and fragment:
                    tcp.sendall(fragment)
                    fragment = b""
            elif opcode == 0x8:
                with self._send_lock:
                    try:
                        send_frame(self.ws, 0x8, payload[:2])
                    except Exception:
                        pass
                return
            elif opcode == 0x9:
                with self._send_lock:
                    try:
                        send_frame(self.ws, 0xA, payload)
                    except Exception:
                        pass
            elif opcode == 0xA:
                continue
            else:
                return

    def _vnc_to_ws(self, tcp):
        try:
            while not self._closed.is_set():
                data = tcp.recv(MAX_FRAME)
                if not data:
                    break
                with self._send_lock:
                    send_frame(self.ws, 0x2, data)
        except Exception:
            pass
        finally:
            self._closed.set()


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "vnc_server/1.0"
    vnc_host = "127.0.0.1"
    vnc_port = 5900

    def do_GET(self):
        if self.headers.get("Upgrade", "").lower() == "websocket":
            return self._handle_websocket()
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/vnc.html")
            self.end_headers()
            return
        super().do_GET()

    def _handle_websocket(self):
        try:
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_error(400, "Missing Sec-WebSocket-Key")
                return
            accept = base64.b64encode(
                hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
            self.send_response_only(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
        except Exception as exc:
            print(f"[error] WebSocket 握手失败: {exc}")
            self.close_connection = True
            return

        proxy = ProxyConnection(self.connection,
                                Handler.vnc_host, Handler.vnc_port)
        proxy.run()
        self.close_connection = True

    def log_message(self, format, *args):
        sys.stderr.write("[http] %s - %s\n" % (self.address_string(), format % args))


def main():
    ap = argparse.ArgumentParser(
        description="noVNC Web 服务端（跨平台，支持 Windows/Linux）")
    ap.add_argument("--host", default="0.0.0.0", help="HTTP 监听地址（默认 0.0.0.0）")
    ap.add_argument("--port", type=int, default=6080, help="HTTP 端口（默认 6080）")
    ap.add_argument("--vnc-host", default="127.0.0.1", help="VNC 服务器地址（默认本机）")
    ap.add_argument("--vnc-port", type=int, default=5900, help="VNC 服务器端口（默认 5900）")
    ap.add_argument("--root", default=None, help="静态文件根目录（默认脚本所在目录）")
    ap.add_argument("--display", default=None,
                    help="要共享的 X 显示，如 :0（默认自动检测本机屏幕）")
    ap.add_argument("--no-auto-vnc", action="store_true",
                    help="不自动启动本机 VNC 服务")
    args = ap.parse_args()

    root = args.root or os.path.dirname(os.path.abspath(__file__))
    Handler.directory = root
    Handler.vnc_host = args.vnc_host
    Handler.vnc_port = args.vnc_port

    if not args.no_auto_vnc:
        ensure_local_vnc(args.vnc_host, args.vnc_port, args.display)

    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"[error] 无法监听 {args.host}:{args.port}: {exc}")
        sys.exit(1)

    print(f"[ok] noVNC Web 服务已启动: http://{args.host}:{args.port}/")
    print(f"[ok] 静态文件根目录: {root}")
    print(f"[ok] VNC 代理目标: {args.vnc_host}:{args.vnc_port} (/websockify)")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] 服务已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
