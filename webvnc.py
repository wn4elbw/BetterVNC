#!/usr/bin/env python3
"""
webvnc.py - Windows 远程管理工具（单文件，自带 VNC Server）

功能：
  1. 自带纯 Python VNC Server（RFB 003.008 协议），共享本机屏幕，无密码
  2. HTTPS 文件管理器：左侧面板，从根目录浏览文件树，
     支持上传 / 下载 / 新建文件夹 / 改名 / 移动 / 打包 zip 下载
  3. 命令行终端：下方面板，直接执行命令并获取输出
  4. 基于 noVNC 的网页客户端，打开即自动连接（无点击连接）

平台：Windows（共享真实屏幕并模拟键鼠输入）。
     非 Windows 环境自动切换为虚拟屏幕演示模式（便于调试预览）。

依赖：仅 Python 3 标准库 + Pillow（运行库）。
      pip install pillow

运行：python webvnc.py [--port 6080] [--vnc-port 5900] [--token xxx]

访问：https://<本机IP>:6080/vnc.html
"""
import argparse
import base64
import ctypes
import hashlib
import io
import json
import locale
import mimetypes
import os
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


def log(msg):
    print(f"[webvnc] {msg}", flush=True)


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
    """Windows 抓真实屏幕；其他平台生成虚拟画面便于调试预览。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._t0 = time.time()
        self.virtual = (not IS_WINDOWS) or (Image is None)

    def grab(self):
        if self.virtual:
            return self._virtual_frame()
        with self._lock:
            from PIL import ImageGrab
            return ImageGrab.grab()

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


# ---------------------------------------------------------------------------
# VNC Server（RFB 003.008）
# ---------------------------------------------------------------------------
class VNCServer:
    """纯 Python RFB 服务器，无密码（SecurityType None），支持 Raw 编码。"""

    def __init__(self, host, port, grabber, input_sink):
        self.host = host
        self.port = port
        self.grabber = grabber
        self.input_sink = input_sink
        self._clients = []

    def serve_forever(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        log(f"VNC Server 监听 {self.host}:{self.port}（无密码）")
        while True:
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            client = VNCClient(conn, self.grabber, self.input_sink)
            self._clients.append(client)
            threading.Thread(target=self._run_client, args=(client,),
                             daemon=True).start()

    def _run_client(self, client):
        try:
            client.run()
        except Exception as exc:
            log(f"VNC 客户端错误: {exc}")
        finally:
            try:
                client.close()
            except Exception:
                pass
            if client in self._clients:
                self._clients.remove(client)


class VNCClient:
    def __init__(self, conn, grabber, input_sink):
        self.conn = conn
        self.grabber = grabber
        self.input_sink = input_sink
        self.prev_data = None
        self.pixel_size = 4
        self._buf = b""

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
        name = b"webvnc"
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
                self._recv(n * 4)
            elif msg_type == 3:
                self._recv(1)
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
                self.input_sink.pointer(x, y, mask)
            elif msg_type == 6:
                self._recv(3)
                n = struct.unpack("!I", self._recv(4))[0]
                self._recv(n)
            else:
                break

    def _parse_pixel_format(self, fmt):
        (bpp, depth, big, true_colour, rmax, gmax, bmax,
         rshift, gshift, bshift) = struct.unpack("!BBBBHHHBBB", fmt[:12])
        self.pixel_size = max(1, bpp // 8)
        self.client_fmt = (bpp, big, true_colour, rshift, gshift, bshift)

    def _pixels(self, img):
        """把 RGB 图像转换为客户端像素格式（默认 32bpp 小端 BGRX）。"""
        fmt = getattr(self, "client_fmt", None)
        bpp, big, true_colour, rshift, gshift, bshift = (
            fmt if fmt else (32, 0, 1, 16, 8, 0))
        if bpp == 32 and true_colour and not big and (rshift, gshift, bshift) == (16, 8, 0):
            return img.tobytes("raw", "BGRX")
        rgb = img.tobytes()
        px = bytearray(len(rgb) * 4)
        for i in range(0, len(rgb), 3):
            r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
            v = (r << rshift) | (g << gshift) | (b << bshift)
            if big:
                px[i:i + 3] = v.to_bytes(3, "big")
            else:
                px[i:i + 3] = v.to_bytes(3, "little")
        return bytes(px)

    def _send_update(self, incremental):
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
            y0 = by
            y1 = min(by + block, h)
            y_start = None
            for bx in range(0, w, block):
                x0 = bx
                x1 = min(bx + block, w)
                changed = False
                for y in range(y0, y1):
                    o0 = y * row_bytes + x0 * stride
                    o1 = y * row_bytes + x1 * stride
                    if prev[o0:o1] != cur[o0:o1]:
                        changed = True
                        break
                if changed:
                    if y_start is None:
                        y_start = y0
                else:
                    if y_start is not None:
                        rects.append((bx - block, y_start, block, y1 - y_start))
                        y_start = None
            if y_start is not None:
                rects.append((w - block, y_start, block, y1 - y_start))
        if len(rects) > 128:
            return [(0, 0, w, h)]
        return rects

    def _send_fbu(self, data, w, h, rects):
        out = bytearray(struct.pack("!BBH", 0, 0, len(rects)))
        row_bytes = w * self.pixel_size
        for (x, y, rw, rh) in rects:
            out += struct.pack("!HHHHI", x, y, rw, rh, 0)
            for yy in range(y, y + rh):
                off = yy * row_bytes + x * self.pixel_size
                out += data[off:off + rw * self.pixel_size]
        self._send(bytes(out))


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
                    elif kv.lower().startswith("filename="):
                        filename = kv[9:].strip('"')
        if filename is not None:
            files.append({"name": name, "filename": filename, "content": content})
        elif name is not None:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


def run_command(command, timeout=300):
    if not command:
        return {"exit_code": 0, "output": ""}
    if IS_WINDOWS:
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", command]
    else:
        cmd = ["/bin/sh", "-c", command]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": "[timeout]" }
    except Exception as exc:
        return {"exit_code": -1, "output": str(exc)}
    raw = proc.stdout + proc.stderr
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode(locale.getpreferredencoding(False), "replace")
    return {"exit_code": proc.returncode, "output": text}


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
    server_version = "webvnc/1.0"
    directory = os.path.dirname(os.path.abspath(__file__))
    vnc_host = "127.0.0.1"
    vnc_port = 5900
    token = None

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
        if path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/vnc.html")
            self.end_headers()
            return
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        self._serve_static()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/cmd":
            return self._api_cmd()
        if path == "/api/fs/upload":
            return self._fs_upload()
        if path == "/api/fs/mkdir":
            return self._fs_mkdir()
        if path == "/api/fs/rename":
            return self._fs_rename()
        if path == "/api/fs/move":
            return self._fs_move()
        return self._send_json({"error": "not found"}, 404)

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
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
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

    # ---- 命令执行 ----
    def _api_cmd(self):
        if not self._check_token():
            return self._send_json({"error": "forbidden"}, 403)
        try:
            data = json.loads(self._read_body() or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "bad json"}, 400)
        command = data.get("command", "")
        timeout = int(data.get("timeout", 300))
        return self._send_json(run_command(command, timeout))

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
    ap = argparse.ArgumentParser(
        description="webvnc - Windows 远程管理工具（VNC + HTTPS 文件管理 + 终端）")
    ap.add_argument("--host", default="0.0.0.0", help="Web 监听地址（默认 0.0.0.0）")
    ap.add_argument("--port", type=int, default=6080, help="HTTPS 端口（默认 6080）")
    ap.add_argument("--vnc-host", default="0.0.0.0", help="VNC Server 监听地址")
    ap.add_argument("--vnc-port", type=int, default=5900, help="VNC 端口（默认 5900）")
    ap.add_argument("--token", default="", help="访问令牌（可选，保护 API）")
    ap.add_argument("--no-https", action="store_true", help="使用 HTTP 而非 HTTPS")
    args = ap.parse_args()

    if not IS_WINDOWS:
        log("非 Windows 平台：启用虚拟屏幕演示模式（键鼠输入不可用）")

    grabber = ScreenGrabber()
    input_sink = WindowsInput() if IS_WINDOWS else NullInput()

    vnc_thread = threading.Thread(
        target=lambda: VNCServer(args.vnc_host, args.vnc_port,
                                 grabber, input_sink).serve_forever(),
        daemon=True)
    vnc_thread.start()
    time.sleep(0.3)

    WebHandler.vnc_host = "127.0.0.1"
    WebHandler.vnc_port = args.vnc_port
    WebHandler.token = args.token or None

    httpd = ThreadingHTTPServer((args.host, args.port), WebHandler)
    if not args.no_https:
        base = os.path.dirname(os.path.abspath(__file__))
        cert_path = os.path.join(base, "cert.pem")
        key_path = os.path.join(base, "key.pem")
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
