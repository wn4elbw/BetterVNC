/* webvnc 主界面脚本：
   分割条拖拽 + 文件树（行内按钮/拖拽上传）+ 移动弹窗 + 命令行
   + 服务端日志 + 三象限分类切换 + 主题 + 屏幕浮动按钮 */
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);

    /* ====================================================================
     * 布局固定：二三四象限尺寸固定（不可拖动，扩大窗口仅扩大预览区）
     * ================================================================== */

    function setupQ3Nav() {
        const btns = document.querySelectorAll(".q3_nav_btn");
        const panes = document.querySelectorAll(".q3_pane");

        function show(btn) {
            btns.forEach((b) => b.classList.toggle("active", b === btn));
            panes.forEach((p) => {
                const on = p.dataset.pane === btn.dataset.pane;
                p.classList.toggle("active", on);
                p.style.display = on ? "block" : "none";
            });
            theme.refreshNav();
        }

        btns.forEach((btn) => btn.addEventListener("click", () => show(btn)));

        /* 初始化：只显示当前激活面板 */
        let active = null;
        panes.forEach((p) => {
            if (p.classList.contains("active")) active = p;
            else p.style.display = "none";
        });
        if (active) active.style.display = "block";
    }

    /* ====================================================================
     * 一象限：屏幕浮动按钮（网页全屏 / 全屏网页，右下角）
     * ================================================================== */
    function setupScreenTools() {
        // 页面内缩放：预览区铺满浏览器窗口（隐藏其他象限），再点恢复
        const layout = $("webvnc_layout");
        const fsIds = ["q_file", "q_ctrl", "q_bottom", "div_v", "div_h"];
        const savedDisplay = {};
        $("st_zoom_btn").addEventListener("click", () => {
            const on = layout.dataset.fs !== "1";
            fsIds.forEach((id) => {
                const el = $(id);
                if (on) {
                    savedDisplay[id] = el.style.display;
                    el.style.display = "none";
                } else {
                    el.style.display = savedDisplay[id] || "";
                }
            });
            const scr = $("q_screen");
            if (on) {
                savedDisplay._scr = scr.style.cssText;
                scr.style.cssText = "position:absolute;left:0;top:0;right:0;bottom:0;background:#1a1b20";
            } else {
                scr.style.cssText = savedDisplay._scr || "";
            }
            layout.dataset.fs = on ? "1" : "";
            $("st_zoom_btn").textContent = on ? "退出缩放" : "缩放";
            window.dispatchEvent(new Event("resize"));
        });
    }

    /* ====================================================================
     * 软键盘 / 小键盘（点击预览区右下角「软键盘」弹出）
     * ================================================================== */
    const onscreenKeyboard = (function () {
        const mask = $("osk_mask");
        const body = $("osk_body");
        const closeBtn = $("osk_close_btn");
        let visible = false;

        const ROWS = [
            ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Back"],
            ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
            ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
            ["Shift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift"],
            ["Ctrl", "Alt", " ", "Alt", "Ctrl"],
        ];
        const NUMPAD = [
            ["NumLock", "KPDiv", "KPMul", "KPSub"],
            ["KP7", "KP8", "KP9", "KPAdd"],
            ["KP4", "KP5", "KP6", "KPAdd"],
            ["KP1", "KP2", "KP3", "KPEnter"],
            ["KP0", "KP0", "KPDec", "KPEnter"],
        ];

        function keyToKeysym(key) {
            // 转 noVNC keysym（部分），简单键直接发送
            const map = {
                "Back": 0xFF08, "Tab": 0xFF09, "Enter": 0xFF0D,
                "Esc": 0xFF1B, "Caps": 0xFFE5, "Shift": 0xFFE1,
                "Ctrl": 0xFFE3, "Alt": 0xFFE9, " ": 0x0020,
                "\\": 0x005C, "'": 0x0027, ";": 0x003B, ",": 0x002C,
                ".": 0x002E, "/": 0x002F, "-": 0x002D, "=": 0x003D,
                "[": 0x005B, "]": 0x005D,
                "NumLock": 0xFF7F, "KPDiv": 0xFFAF, "KPMul": 0xFFAA,
                "KPSub": 0xFFAD, "KPAdd": 0xFFAB, "KPDec": 0xFFAE,
                "KPEnter": 0xFF8D,
            };
            if (map[key] !== undefined) return map[key];
            // 小键盘数字：KP_0..KP_9 = 0xFFB0..0xFFB9
            if (/^KP([0-9])$/.test(key)) {
                return 0xFFB0 + parseInt(key.slice(2), 10);
            }
            // F1-F12
            if (/^F(1[0-2]|[1-9])$/.test(key)) {
                return 0xFFBE + (parseInt(key.slice(1), 10) - 1);
            }
            // 小键盘数字（独立 keysym，与主键盘区分）
            if (/^[0-9]$/.test(key)) {
                return key.charCodeAt(0);
            }
            const ch = key.charCodeAt(0);
            return ch;
        }

        function press(key) {
            const ui = window.UI;
            if (!ui || !ui.rfb || typeof ui.rfb.sendKey !== "function") return;
            try {
                const ks = keyToKeysym(key);
                ui.rfb.sendKey(ks, true);
                ui.rfb.sendKey(ks, false);
            } catch (err) { /* 忽略 */ }
        }

        function render() {
            body.innerHTML = "";
            const t = theme.palette();
            const kb = document.createElement("div");
            kb.style.cssText = "display:flex;flex-direction:column;gap:6px";
            for (const row of ROWS) {
                const r = document.createElement("div");
                r.style.cssText = "display:flex;gap:6px";
                for (const k of row) {
                    const b = document.createElement("button");
                    b.textContent = k;
                    const wide = ["Back", "Tab", "Caps", "Enter", "Shift", "Ctrl", "Alt", " "].includes(k);
                    b.style.cssText = "flex:" + (k === " " ? "6" : wide ? "1.6" : "1") +
                        ";padding:8px 4px;background:" + t.panel +
                        ";border:1px solid " + t.input + ";border-radius:6px;color:" + t.fg +
                        ";font-size:13px;cursor:pointer;font-family:inherit";
                    if (k === " ") b.style.minHeight = "32px";
                    b.addEventListener("click", () => press(k));
                    r.appendChild(b);
                }
                kb.appendChild(r);
            }
            const sep = document.createElement("div");
            sep.style.cssText = "height:1px;background:" + t.border + ";margin:4px 0";
            kb.appendChild(sep);
            const npTitle = document.createElement("div");
            npTitle.textContent = "小键盘";
            npTitle.style.cssText = "color:" + t.muted + ";font-size:12px";
            kb.appendChild(npTitle);
            for (const row of NUMPAD) {
                const r = document.createElement("div");
                r.style.cssText = "display:flex;gap:6px";
                for (const k of row) {
                    const b = document.createElement("button");
                    const label = { "KP0": "0", "KP1": "1", "KP2": "2", "KP3": "3",
                        "KP4": "4", "KP5": "5", "KP6": "6", "KP7": "7",
                        "KP8": "8", "KP9": "9", "KPDiv": "/", "KPMul": "*",
                        "KPSub": "-", "KPAdd": "+", "KPDec": ".", "KPEnter": "Enter",
                        "NumLock": "NumLock" }[k] || k;
                    b.textContent = label;
                    const wide = ["KP0", "KPEnter", "NumLock"].includes(k);
                    b.style.cssText = "flex:" + (wide ? "2" : "1") +
                        ";padding:8px 4px;background:" + t.panel +
                        ";border:1px solid " + t.input + ";border-radius:6px;color:" + t.fg +
                        ";font-size:13px;cursor:pointer;font-family:inherit";
                    b.addEventListener("click", () => press(k));
                    r.appendChild(b);
                }
                kb.appendChild(r);
            }
            body.appendChild(kb);
        }

        function show() {
            if (!mask || !body) return;
            visible = true;
            render();
            mask.style.display = "block";
        }

        function hide() {
            if (!mask) return;
            visible = false;
            mask.style.display = "none";
        }

        function init() {
            if (!mask || !closeBtn) return;
            $("st_kbd_btn").addEventListener("click", () => {
                if (visible) hide();
                else show();
            });
            closeBtn.addEventListener("click", hide);
            document.addEventListener("wv-theme-change", () => { if (visible) render(); });
        }

        return { init };
    })();

    /* ====================================================================
     * 三象限：缩放调整（原始 / 适配 / 远程）
     * ================================================================== */
    function setupZoom() {
        const sel = $("noVNC_setting_resize");
        const btns = document.querySelectorAll(".zoom_btn");

        function sync() {
            const t = theme.palette();
            btns.forEach((b) => {
                const on = b.dataset.mode === sel.value;
                b.classList.toggle("active", on);
                if (on) {
                    b.style.background = t.navactive;
                    b.style.borderColor = t.navactiveborder;
                    b.style.color = "#ffffff";
                } else {
                    b.style.background = t.panel;
                    b.style.borderColor = t.input;
                    b.style.color = t.fg;
                }
            });
        }

        btns.forEach((b) => {
            b.addEventListener("click", () => {
                sel.value = b.dataset.mode;
                sel.dispatchEvent(new Event("change", { bubbles: true }));
                sync();
            });
        });
        sel.addEventListener("change", sync);
        sync();
    }

    /* ====================================================================
     * 三象限：连接信息面板（__WEBVNC__ 注入 + 实时状态）
     * ================================================================== */
    function setupConnPane() {
        const s = window.__WEBVNC__ || {};
        const txt = (id, v) => { const el = $(id); if (el && v !== undefined) el.textContent = v; };
        txt("conn_host", s.vnc_host || "-");
        txt("conn_port", s.vnc_port || "-");
        txt("conn_encrypt", s.encrypt ? "WSS (加密)" : "WS");
        txt("conn_platform", s.platform || "-");
    }

    /* ====================================================================
     * 主题：深色 / 浅色两种预设，选择保存到服务端配置文件
     * 不允许修改具体颜色
     * ================================================================== */
    const theme = (function () {
        const THEMES = {
            dark: {
                bg: "#2b2e33", fg: "#ffffff", border: "#626a76",
                bar: "#3d4149", panel: "#33373d", input: "#4a4e56",
                sel: "#3d4148", selfg: "#ffffff", muted: "#b6bac2",
                nav: "#23252a", navfg: "#e8e8ec", navhover: "#3a3e45",
                navhoverfg: "#ffffff", navactive: "#4a4f58",
                navactiveborder: "#6a7080", screen: "#1a1b20",
                accent: "#636a75", accentfg: "#ffffff",
            },
            light: {
                bg: "#eceef0", fg: "#1c1f23", border: "#a8aeb6",
                bar: "#c6cbd2", panel: "#ffffff", input: "#aeb4bd",
                sel: "#dde0e6", selfg: "#1c1f23", muted: "#6f747d",
                nav: "#dfe2e5", navfg: "#1c1f23", navhover: "#3a3d42",
                navhoverfg: "#ffffff", navactive: "#4a4f58",
                navactiveborder: "#6a7080", screen: "#d3d6da",
                accent: "#636a75", accentfg: "#ffffff",
            },
        };
        let current = "dark";

        function palette() { return THEMES[current]; }

        function applyTo(el, t) {
            const spec = el.getAttribute("data-th");
            if (!spec) return;
            t = t || THEMES[current];
            spec.split(";").forEach((pair) => {
                const i = pair.indexOf(":");
                if (i < 0) return;
                const prop = pair.slice(0, i).trim();
                const key = pair.slice(i + 1).trim();
                if (t[key] !== undefined) el.style[prop] = t[key];
            });
        }

        function refreshNav() {
            const t = THEMES[current];
            document.querySelectorAll(".q3_nav_btn").forEach((b) => {
                if (b.classList.contains("active")) {
                    b.style.background = t.navactive;
                    b.style.color = "#ffffff";
                } else {
                    b.style.background = "transparent";
                    b.style.color = t.navfg;
                }
            });
        }

        function refreshActive() {
            const t = THEMES[current];
            document.querySelectorAll(".zoom_btn.active, .theme_btn.active").forEach((b) => {
                b.style.background = t.navactive;
                b.style.borderColor = t.navactiveborder;
                b.style.color = "#ffffff";
            });
        }

        function apply(name) {
            current = THEMES[name] ? name : "dark";
            const t = THEMES[current];
            document.querySelectorAll("[data-th]").forEach((el) => applyTo(el, t));
            document.documentElement.classList.toggle("theme-dark", current === "dark");
            document.documentElement.classList.toggle("theme-light", current === "light");
            refreshNav();
            refreshActive();
            /* 通知动态内容（文件行/终端输出）按新主题重绘 */
            document.dispatchEvent(new CustomEvent("wv-theme-change"));
        }

        function syncUI() {
            document.querySelectorAll(".theme_btn").forEach((b) => {
                b.classList.toggle("active", b.dataset.theme === current);
            });
            refreshActive();
        }

        /* hover 效果（内联写死样式下用 JS 事件委托实现） */
        function bindHover() {
            const t = () => THEMES[current];
            const out = (el) => {
                if (el.classList.contains("fm_empty")) return;
                if (el.classList.contains("selected")) {
                    el.style.background = t().sel;
                    el.style.color = t().selfg;
                } else {
                    el.style.background = "transparent";
                    el.style.color = t().fg;
                }
            };
            document.addEventListener("mouseover", (ev) => {
                const nav = ev.target.closest(".q3_nav_btn");
                if (nav) {
                    if (nav.classList.contains("active")) return;
                    nav.style.background = t().navhover;
                    nav.style.color = t().navhoverfg;
                    return;
                }
                const item = ev.target.closest(".fm_item");
                if (item) {
                    if (item.classList.contains("fm_empty")) return;
                    item.style.background = t().sel;
                    item.style.color = t().selfg;
                    return;
                }
                const mv = ev.target.closest(".mv_item");
                if (mv) { mv.style.background = t().sel; mv.style.color = t().selfg; return; }
                const pb = ev.target.closest(".path_btn");
                if (pb) { pb.style.background = t().sel; pb.style.color = t().selfg; return; }
                const rb = ev.target.closest(".row_btn");
                if (rb) { rb.style.background = t().accent; rb.style.color = t().accentfg; return; }
            });
            document.addEventListener("mouseout", (ev) => {
                const nav = ev.target.closest(".q3_nav_btn");
                if (nav) {
                    refreshNav();
                    return;
                }
                const item = ev.target.closest(".fm_item");
                if (item) { out(item); return; }
                const mv = ev.target.closest(".mv_item");
                if (mv) {
                    mv.style.background = mv.classList.contains("selected") ? t().sel : "transparent";
                    mv.style.color = mv.classList.contains("selected") ? t().selfg : t().fg;
                    return;
                }
                const pb = ev.target.closest(".path_btn");
                if (pb) { pb.style.background = "transparent"; pb.style.color = t().fg; return; }
                const rb = ev.target.closest(".row_btn");
                if (rb) { rb.style.background = "transparent"; rb.style.color = t().fg; return; }
            });
        }

        function load() {
            fetch("/api/theme")
                .then((r) => r.ok ? r.json() : { theme: "dark" })
                .then((d) => {
                    apply(d.theme === "light" ? "light" : "dark");
                    syncUI();
                    hideLoading();
                })
                .catch(() => {
                    apply("dark");
                    syncUI();
                    hideLoading();
                });
        }

        function set(name) {
            apply(name);
            syncUI();
            fetch("/api/theme", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ theme: name }),
            }).catch(() => { /* 保存失败忽略 */ });
        }

        function init() {
            document.querySelectorAll(".theme_btn").forEach((b) => {
                b.addEventListener("click", () => set(b.dataset.theme));
            });
            bindHover();
            load();
        }

        return { init, set, palette, refreshNav };
    })();

    /* ====================================================================
     * 文件树（二象限）
     * ================================================================== */
    const fm = (function () {
        const state = { path: "", items: [], selected: new Set(), drives: [] };
        const tree = $("fm_tree");
        const pathText = $("fm_path_text");
        const status = $("fm_status");
        const promptBox = { el: null, label: null, input: null, callback: null };
        let confirmTimer = null;

        function fmtSize(n) {
            if (n < 1024) return n + " B";
            const units = ["KB", "MB", "GB", "TB"];
            let v = n, u = -1;
            do { v /= 1024; u += 1; } while (v >= 1024 && u < units.length - 1);
            return v.toFixed(1) + " " + units[u];
        }

        async function api(url, opts) {
            const resp = await fetch(url, opts);
            const ct = resp.headers.get("Content-Type") || "";
            if (ct.includes("application/json")) return await resp.json();
            return resp;
        }

        function setStatus(msg) { status.textContent = msg; }

        function joinPath(dir, name) {
            if (!dir) return name;
            if (dir.endsWith("/") || dir.endsWith("\\")) return dir + name;
            return dir + "/" + name;
        }

        function updateNav() {
            $("fm_up_btn").disabled = (state.path === "");
        }

        /* ---- 内联输入条（新建/改名） ---- */
        function promptInline(labelText, defaultValue, onOk) {
            promptBox.label.textContent = labelText;
            promptBox.input.value = defaultValue || "";
            promptBox.callback = onOk;
            promptBox.el.style.display = "flex";
            promptBox.input.focus();
            promptBox.input.select();
        }
        function promptClose() {
            promptBox.el.style.display = "none";
            promptBox.callback = null;
        }
        function promptConfirm() {
            const value = promptBox.input.value.trim();
            const cb = promptBox.callback;
            promptClose();
            if (value && cb) cb(value);
        }

        /* ---- 行内操作 ---- */
        function rowButton(text, title, cls, onClick) {
            const t = theme.palette();
            const b = document.createElement("button");
            b.className = "row_btn" + (cls ? " " + cls : "");
            b.textContent = text;
            b.title = title;
            b.style.cssText = "background:transparent;border:none;padding:0;margin:0;" +
                "width:15px;height:15px;display:inline-flex;align-items:center;justify-content:center;" +
                "color:" + t.muted + ";font-size:13px;cursor:pointer;line-height:1;" +
                "font-family:inherit;white-space:nowrap;min-width:0";
            b.addEventListener("click", (ev) => {
                ev.stopPropagation();
                onClick(b);
            });
            return b;
        }

        function downloadPath(p) {
            const a = document.createElement("a");
            a.href = "/api/fs/download?path=" + encodeURIComponent(p);
            a.download = "";
            document.body.appendChild(a);
            a.click();
            a.remove();
        }

        function zipDownload(paths) {
            const query = paths.map((p) => encodeURIComponent(p)).join(",");
            const a = document.createElement("a");
            a.href = "/api/fs/zip?paths=" + query;
            a.download = "webvnc.zip";
            document.body.appendChild(a);
            a.click();
            a.remove();
            setStatus("已开始下载 zip");
        }

        function doDelete(p) {
            api("/api/fs/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ paths: [p] }),
            }).then((res) => {
                setStatus(res.ok ? "已删除" : ("删除失败: " + res.error));
                load(state.path);
            }).catch((err) => setStatus("删除失败: " + err));
        }

        function deleteButton(p) {
            /* 删除（✕）→ 点击后变 ✓（红底）要求再次确认，再点执行删除 */
            return rowButton("\u2715", "删除（点击两次确认）", "danger", (btn) => {
                if (btn.classList.contains("confirm")) {
                    clearTimeout(confirmTimer);
                    btn.style.background = "transparent";
                    btn.style.color = theme.palette().muted;
                    doDelete(p);
                    return;
                }
                btn.classList.add("confirm");
                btn.textContent = "\u2713";
                btn.style.background = "#a03030";
                btn.style.color = "#ffffff";
                btn.style.borderRadius = "2px";
                btn.style.padding = "0 2px";
                confirmTimer = setTimeout(() => {
                    btn.classList.remove("confirm");
                    btn.textContent = "\u2715";
                    btn.style.background = "transparent";
                    btn.style.color = theme.palette().muted;
                    btn.style.padding = "0";
                }, 2500);
            });
        }

        function renameItem(p) {
            const oldName = p.split(/[\\/]/).pop();
            promptInline("新名称:", oldName, (newName) => {
                if (newName === oldName) return;
                api("/api/fs/rename", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path: p, new_name: newName }),
                }).then((res) => {
                    setStatus(res.ok ? "已重命名" : ("失败: " + res.error));
                    load(state.path);
                }).catch((err) => setStatus("失败: " + err));
            });
        }

        /* ---- 移动弹窗 ---- */
        function moveItems(paths) {
            moveDialog.open(paths);
        }

        /* ---- 渲染（事件委托版） ---- */
        function buildRow(item) {
            const t = theme.palette();
            const p = joinPath(state.path, item.name);
            const row = document.createElement("div");
            row.className = "fm_item" + (item.is_dir ? " dir" : " file");
            row.dataset.name = item.name;
            row.style.cssText = "display:flex;align-items:center;gap:2px;padding:1px 6px;cursor:pointer;white-space:nowrap;color:" + t.fg;

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "fm_check";
            cb.checked = state.selected.has(item.name);
            cb.style.cssText = "accent-color:" + t.accent + ";width:12px;height:12px;flex:0 0 auto";

            const icon = document.createElement("span");
            icon.className = "fm_icon";
            icon.textContent = item.is_dir ? "\u25A3" : "\u25A2";
            icon.style.cssText = "width:14px;text-align:center;flex:0 0 auto;color:" +
                (item.is_dir ? "#b8860b" : "#7d8a99");

            const name = document.createElement("span");
            name.className = "fm_name";
            name.title = item.name;
            name.textContent = item.name + (item.is_dir ? "/" : "");
            name.style.cssText = "flex:1;overflow:hidden;text-overflow:ellipsis;min-width:0;color:" + t.fg;

            const size = document.createElement("span");
            size.className = "fm_size";
            size.textContent = item.is_dir ? "" : fmtSize(item.size);
            size.style.cssText = "flex:0 0 auto;font-size:11px;color:" + t.muted;

            const btns = document.createElement("span");
            btns.className = "row_btns";
            btns.style.cssText = "display:grid;grid-template-columns:repeat(4,15px);gap:1px;flex:0 0 auto;justify-content:end;align-items:center;padding:0;margin:0";
            if (item.is_dir) {
                btns.appendChild(rowButton("\u2193", "打包 zip 下载", "zip", () => {
                    zipDownload([p]);
                }));
            } else {
                btns.appendChild(rowButton("\u2193", "下载文件", "down", () => {
                    downloadPath(p);
                }));
            }
            btns.appendChild(rowButton("\u270E", "重命名", "rename", () => renameItem(p)));
            btns.appendChild(rowButton("\u2192", "移动到目录", "move", () => moveItems([p])));
            btns.appendChild(deleteButton(p));

            row.appendChild(cb);
            row.appendChild(icon);
            row.appendChild(name);
            row.appendChild(size);
            row.appendChild(btns);
            return row;
        }

        function render() {
            pathText.textContent = state.path || "(根目录)";
            updateNav();
            tree.innerHTML = "";
            if (state.items.length === 0) {
                const empty = document.createElement("div");
                empty.className = "fm_item fm_empty";
                empty.textContent = "(空目录)";
                empty.style.cssText = "display:flex;align-items:center;padding:2px 6px;color:" + theme.palette().muted;
                tree.appendChild(empty);
                setStatus("0 项");
                return;
            }
            const frag = document.createDocumentFragment();
            for (const item of state.items) {
                frag.appendChild(buildRow(item));
            }
            tree.appendChild(frag);
            setStatus(state.items.length + " 项" +
                      (state.selected.size ? "，已选 " + state.selected.size : ""));
        }

        /* ---- 树级事件委托（单击选中 / 复选 / 双击进入） ---- */
        function styleRow(row, sel) {
            const t = theme.palette();
            row.style.background = sel ? t.sel : "transparent";
            row.style.color = sel ? t.selfg : t.fg;
        }

        function bindTreeEvents() {
            tree.addEventListener("click", (ev) => {
                const row = ev.target.closest(".fm_item");
                if (!row || !row.dataset.name) return;
                if (ev.target.classList.contains("fm_check")) return;
                if (ev.target.classList.contains("row_btn")) return;

                const item = state.items.find((i) => i.name === row.dataset.name);
                if (!item) return;

                const mult = ev.ctrlKey || ev.metaKey || ev.shiftKey;
                if (!mult) {
                    tree.querySelectorAll(".fm_item.selected").forEach((r) => {
                        if (r !== row) { r.classList.remove("selected"); styleRow(r, false); }
                    });
                    state.selected.clear();
                    row.querySelector(".fm_check").checked = true;
                    state.selected.add(item.name);
                } else {
                    const cb = row.querySelector(".fm_check");
                    cb.checked = !cb.checked;
                    if (cb.checked) state.selected.add(item.name);
                    else state.selected.delete(item.name);
                }
                row.classList.add("selected");
                styleRow(row, true);
                setStatus(state.items.length + " 项，已选 " + state.selected.size);
            });

            tree.addEventListener("change", (ev) => {
                const cb = ev.target;
                if (!cb.classList.contains("fm_check")) return;
                const row = cb.closest(".fm_item");
                if (!row || !row.dataset.name) return;
                const name = row.dataset.name;
                if (cb.checked) {
                    state.selected.add(name);
                    row.classList.add("selected");
                    styleRow(row, true);
                } else {
                    state.selected.delete(name);
                    row.classList.remove("selected");
                    styleRow(row, false);
                }
                setStatus(state.items.length + " 项，已选 " + state.selected.size);
            });

            tree.addEventListener("dblclick", (ev) => {
                const row = ev.target.closest(".fm_item");
                if (!row || !row.dataset.name) return;
                if (ev.target.classList.contains("row_btn")) return;
                const item = state.items.find((i) => i.name === row.dataset.name);
                if (!item) return;
                if (item.is_dir) {
                    state.selected.clear();
                    load(joinPath(state.path, item.name));
                } else {
                    downloadPath(joinPath(state.path, item.name));
                }
            });
        }

        async function load(path) {
            try {
                const res = await api("/api/fs/list?path=" +
                                      encodeURIComponent(path || ""));
                if (res.error) { setStatus("错误: " + res.error); return; }
                state.path = res.path || path;
                state.items = res.items || [];
                state.selected.clear();
                render();
            } catch (err) {
                setStatus("请求失败: " + err);
            }
        }

        async function refresh() { await load(state.path); }

        async function goUp() {
            if (state.path === "") return; /* 根目录下点击无效 */
            const res = await api("/api/fs/list?path=" +
                                  encodeURIComponent(state.path));
            if (res.parent) await load(res.parent);
        }

        async function showRoot() {
            try {
                const res = await api("/api/fs/drives");
                state.drives = res.drives || [];
                state.path = "";
                state.items = state.drives.map((d) => ({
                    name: d, is_dir: true, size: 0, mtime: 0,
                }));
                state.selected.clear();
                render();
                pathText.textContent = "(根目录)";
            } catch (err) {
                setStatus("加载根目录失败: " + err);
            }
        }

        /* ---- 上传（按钮 + 拖拽） ---- */
        function uploadFiles(fileList) {
            if (!fileList.length) return;
            if (state.path === "") {
                setStatus("请先进入一个目录再上传");
                return;
            }
            const fd = new FormData();
            for (const f of fileList) fd.append("file", f);
            setStatus("上传中...");
            api("/api/fs/upload?path=" + encodeURIComponent(state.path),
                { method: "POST", body: fd })
                .then((res) => {
                    setStatus(res.error ? ("上传失败: " + res.error)
                            : ("已上传: " + (res.saved || []).join(", ")));
                    refresh();
                }).catch((err) => setStatus("上传失败: " + err));
        }

        function setupDragDrop() {
            ["dragenter", "dragover"].forEach((evName) => {
                tree.addEventListener(evName, (ev) => {
                    ev.preventDefault();
                    tree.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach((evName) => {
                tree.addEventListener(evName, () => tree.classList.remove("dragover"));
            });
            tree.addEventListener("drop", (ev) => {
                ev.preventDefault();
                uploadFiles(ev.dataTransfer.files);
            });
        }

        function selectedPaths() {
            const paths = Array.from(state.selected)
                .map((n) => joinPath(state.path, n));
            if (paths.length === 0) {
                setStatus("请先勾选文件或文件夹");
                return null;
            }
            return paths;
        }

        function init() {
            promptBox.el = $("fm_prompt");
            promptBox.label = $("fm_prompt_label");
            promptBox.input = $("fm_prompt_input");
            $("fm_prompt_ok").addEventListener("click", promptConfirm);
            $("fm_prompt_cancel").addEventListener("click", promptClose);
            promptBox.input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") { ev.preventDefault(); promptConfirm(); }
                else if (ev.key === "Escape") { ev.preventDefault(); promptClose(); }
            });

            $("fm_refresh_btn").addEventListener("click", refresh);
            $("fm_home_btn").addEventListener("click", showRoot);
            $("fm_up_btn").addEventListener("click", goUp);
            $("fm_upload_btn").addEventListener("click", () => {
                const input = $("fm_file_input");
                input.value = "";
                input.click();
            });
            $("fm_file_input").addEventListener("change", (ev) =>
                uploadFiles(ev.target.files));
            $("fm_mkdir_btn").addEventListener("click", () => {
                promptInline("新建文件夹名称:", "", (name) => {
                    setStatus("创建中...");
                    api("/api/fs/mkdir", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ path: joinPath(state.path, name) }),
                    }).then((res) => {
                        setStatus(res.ok ? "已创建" : ("失败: " + res.error));
                        refresh();
                    }).catch((err) => setStatus("失败: " + err));
                });
            });
            $("fm_zip_btn").addEventListener("click", () => {
                const paths = selectedPaths();
                if (paths) zipDownload(paths);
            });
            bindTreeEvents();
            setupDragDrop();
            showRoot();
            /* 主题切换后重新渲染文件行（内联颜色按新主题） */
            document.addEventListener("wv-theme-change", () => {
                if (state.items.length) render();
            });
        }

        return { init };
    })();

    /* ====================================================================
     * 移动弹窗（蒙版 + 目录选择）
     * ================================================================== */
    const moveDialog = (function () {
        const mv = { path: "", parent: null, items: [], pick: null, targets: [] };
        const mask = $("move_mask");
        const dlg = $("move_dlg");
        const treeEl = $("mv_tree");

        async function api(url, opts) {
            const resp = await fetch(url, opts);
            return await resp.json();
        }

        function render() {
            const t = theme.palette();
            $("mv_path_text").textContent = mv.path || "(根目录)";
            $("mv_up_btn").disabled = !mv.parent;
            treeEl.innerHTML = "";
            if (mv.items.length === 0) {
                const empty = document.createElement("div");
                empty.className = "mv_item";
                empty.style.cssText = "display:flex;align-items:center;gap:6px;padding:3px 12px;color:" + t.muted;
                empty.textContent = "(无子目录)";
                treeEl.appendChild(empty);
            }
            for (const item of mv.items) {
                if (!item.is_dir) continue;
                const row = document.createElement("div");
                row.className = "mv_item";
                row.style.cssText = "display:flex;align-items:center;gap:6px;padding:3px 12px;cursor:pointer;white-space:nowrap;color:" + t.fg;
                const icon = document.createElement("span");
                icon.style.color = "#b8860b";
                icon.textContent = "\u25A3";
                const name = document.createElement("span");
                name.textContent = item.name + "/";
                row.appendChild(icon);
                row.appendChild(name);
                const p = mv.path ? mv.path.replace(/[\/\\]$/, "") + "/" + item.name
                                  : item.name;
                row.addEventListener("click", () => {
                    treeEl.querySelectorAll(".mv_item")
                        .forEach((r) => {
                            r.classList.remove("selected");
                            r.style.background = "transparent";
                            r.style.color = theme.palette().fg;
                        });
                    row.classList.add("selected");
                    row.style.background = theme.palette().sel;
                    row.style.color = theme.palette().selfg;
                    mv.pick = p;
                });
                row.addEventListener("dblclick", () => loadDir(p));
                treeEl.appendChild(row);
            }
        }

        async function loadDir(path) {
            const res = await api("/api/fs/list?path=" +
                                  encodeURIComponent(path || ""));
            if (res.error) return;
            mv.path = res.path || path;
            mv.parent = res.parent || null;
            mv.items = res.items || [];
            mv.pick = mv.path;
            render();
        }

        async function showRoot() {
            const res = await api("/api/fs/drives");
            mv.path = "";
            mv.parent = null;
            mv.items = (res.drives || []).map((d) => ({
                name: d, is_dir: true,
            }));
            mv.pick = null;
            render();
        }

        function open(targets) {
            mv.targets = targets;
            mask.style.display = "block";
            dlg.style.display = "flex";
            showRoot();
        }

        function close() {
            mask.style.display = "none";
            dlg.style.display = "none";
        }

        function init() {
            $("mv_home_btn").addEventListener("click", showRoot);
            $("mv_up_btn").addEventListener("click", () => {
                if (mv.parent) loadDir(mv.parent);
            });
            $("mv_cancel_btn").addEventListener("click", close);
            $("mv_ok_btn").addEventListener("click", () => {
                if (!mv.pick) return;
                const dest = mv.pick;
                const targets = mv.targets;
                close();
                api("/api/fs/move", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ paths: targets, dest: dest }),
                }).then((res) => {
                    $("fm_status").textContent = res.ok
                        ? ("已移动 " + res.moved.length + " 项")
                        : ("移动失败: " + res.error);
                    /* 刷新文件树 */
                    $("fm_refresh_btn").click();
                }).catch((err) => {
                    $("fm_status").textContent = "移动失败: " + err;
                });
            });
            /* 主题切换后重渲染目录行（弹窗打开时） */
            document.addEventListener("wv-theme-change", () => {
                if (dlg.style.display === "flex") render();
            });
        }

        return { init, open };
    })();

    /* ====================================================================
     * 四象限：命令行（作业轮询）
     * ================================================================== */
    const term = (function () {
        const output = $("term_output");
        const input = $("term_input");
        let currentJob = null;

        function appendLine(cls, text) {
            const t = theme.palette();
            const div = document.createElement("div");
            div.className = cls;
            div.textContent = text;
            if (cls === "term_prompt") div.style.color = t.accent;
            else div.style.color = t.fg;
            output.appendChild(div);
            output.scrollTop = output.scrollHeight;
        }

        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

        async function stopJob() {
            if (!currentJob) return;
            try {
                await fetch("/api/cmd/kill", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: currentJob }),
                });
            } catch (err) { /* 忽略 */ }
        }

        async function pollJob(jobId) {
            const seq = { v: 0 };
            for (;;) {
                await sleep(400);
                let data;
                try {
                    const resp = await fetch(
                        "/api/cmd/result?id=" + encodeURIComponent(jobId) +
                        "&seq=" + seq.v);
                    if (resp.status === 404) {
                        appendLine("term_out", "[作业已过期或不存在]");
                        return;
                    }
                    data = await resp.json();
                } catch (err) {
                    appendLine("term_out", "[获取输出失败] " + err);
                    return;
                }
                if (data.output) {
                    appendLine("term_out", data.output);
                    seq.v += data.output.length;
                }
                if (data.done) {
                    if (typeof data.exit_code === "number") {
                        appendLine("term_prompt",
                                   "\u23CE 退出码: " + data.exit_code);
                    }
                    return;
                }
            }
        }

        async function execute() {
            const command = input.value.trim();
            if (!command || currentJob) return;
            input.value = "";
            appendLine("term_prompt", "\u25B6 " + command);
            try {
                const resp = await fetch("/api/cmd", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ command: command, timeout: 300 }),
                });
                const data = await resp.json();
                if (!data.job) {
                    appendLine("term_out", "[提交失败] " + (data.error || "未知错误"));
                    return;
                }
                currentJob = data.job;
                $("term_send_btn").disabled = true;
                $("term_stop_btn").disabled = false;
                $("term_stop_btn").style.opacity = "1";
                $("term_stop_btn").style.background = "#a03030";
                await pollJob(data.job);
            } catch (err) {
                appendLine("term_out", "[请求失败] " + err);
            } finally {
                currentJob = null;
                $("term_send_btn").disabled = false;
                $("term_stop_btn").disabled = true;
                $("term_stop_btn").style.opacity = "0.45";
            }
        }

        async function init() {
            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") { ev.preventDefault(); execute(); }
            });
            $("term_send_btn").addEventListener("click", execute);
            $("term_stop_btn").addEventListener("click", stopJob);
            $("term_clear_btn").addEventListener("click", () => {
                // 清屏但保留首行系统信息
                const first = output.querySelector("div");
                const head = first ? first.textContent : "";
                output.innerHTML = "";
                if (head) {
                    const d = document.createElement("div");
                    d.className = "term_prompt";
                    d.textContent = head;
                    d.style.color = theme.palette().accent;
                    output.appendChild(d);
                }
            });
            try {
                const resp = await fetch("/api/info");
                const info = await resp.json();
                let head = "webvnc " + info.platform + " / Python " + info.python;
                head += info.windows ? " / Windows 屏幕共享已启用"
                                     : " / 虚拟屏幕演示模式";
                if (info.hostname) head += " / " + info.hostname;
                appendLine("term_prompt", head);
            } catch (err) {
                appendLine("term_out", "[初始化失败] " + err);
            }
            /* 主题切换后重着色历史输出 */
            document.addEventListener("wv-theme-change", () => {
                const t = theme.palette();
                output.querySelectorAll("div").forEach((d) => {
                    d.style.color = d.classList.contains("term_prompt")
                        ? t.accent : t.fg;
                });
            });
        }

        return { init };
    })();

    /* ====================================================================
     * 四象限：服务端日志（轮询 /api/log/tail，清屏时服务端新建日志文件）
     * ================================================================== */
    const srvlog = (function () {
        const output = $("log_output");
        let timer = null;
        let cursor = -1;
        let file = "";

        async function poll() {
            try {
                const q = cursor >= 0 ? `?start=${cursor}` : "?lines=300";
                const resp = await fetch("/api/log/tail" + q);
                if (!resp.ok) return;
                const data = await resp.json();
                if (data.file && data.file !== file) {
                    file = data.file;
                    output.innerHTML = "";
                    cursor = -1;
                }
                const nearBottom =
                    output.scrollTop + output.clientHeight >=
                    output.scrollHeight - 30;
                if (cursor < 0) {
                    output.innerHTML = "";
                    cursor = 0;
                }
                for (const line of data.lines) {
                    const div = document.createElement("div");
                    div.className = "log_line";
                    div.textContent = line;
                    output.appendChild(div);
                }
                cursor = data.next;
                if (nearBottom) output.scrollTop = output.scrollHeight;
            } catch (err) { /* 服务暂不可用 */ }
        }

        async function newLogFile() {
            /* 清屏：让服务端创建新的时间戳日志文件，前端重置游标 */
            try {
                await fetch("/api/log/new", { method: "POST" });
            } catch (err) { /* 忽略 */ }
            file = "";
            cursor = -1;
            output.innerHTML = "";
            poll();
        }

        function init() {
            $("log_clear_btn").addEventListener("click", newLogFile);
            poll();
            timer = setInterval(poll, 2000);
        }

        return { init };
    })();

    /* ====================================================================
     * 服务端日志标题栏：VNC 连接状态 + 连接/断开按钮（互转）
     * ================================================================== */
    /* ====================================================================
     * 三象限：端口面板（扫描展示本机所有开放端口）
     * ================================================================== */
    const portPanel = (function () {
        const listEl = $("port_list");
        let timer = null;
        let ports = [];

        function render() {
            const t = theme.palette();
            if (!listEl) return;
            listEl.innerHTML = "";
            if (!ports.length) {
                const d = document.createElement("div");
                d.textContent = "(无监听端口)";
                d.style.color = t.muted;
                listEl.appendChild(d);
                return;
            }
            const frag = document.createDocumentFragment();
            for (const p of ports) {
                const row = document.createElement("div");
                row.style.cssText = "display:flex;gap:6px;padding:1px 0;" +
                    "white-space:nowrap;color:" + t.fg + ";font-size:11px";
                const b = document.createElement("b");
                b.textContent = String(p.port);
                b.style.cssText = "min-width:44px;font-weight:600;color:" + t.fg;
                const proto = document.createElement("span");
                proto.textContent = p.proto;
                proto.style.cssText = "min-width:34px;color:" + t.muted;
                const addr = document.createElement("span");
                addr.textContent = p.addr;
                addr.style.cssText = "overflow:hidden;text-overflow:ellipsis;color:" + t.muted;
                row.appendChild(b);
                row.appendChild(proto);
                row.appendChild(addr);
                frag.appendChild(row);
            }
            listEl.appendChild(frag);
        }

        async function load() {
            try {
                const resp = await fetch("/api/netstat");
                if (!resp.ok) return;
                const data = await resp.json();
                ports = data.ports || [];
            } catch (err) { /* 忽略 */ }
            render();
        }

        function init() {
            if (!listEl) return;
            /* 切换到端口面板时立即刷新 */
            document.addEventListener("click", (ev) => {
                const btn = ev.target.closest('.q3_nav_btn[data-pane="port"]');
                if (btn) load();
            });
            document.addEventListener("wv-theme-change", render);
            load();
            timer = setInterval(load, 60000);
        }

        return { init };
    })();

    const connStatus = (function () {
        const dot = $("log_conn_dot");
        const text = $("log_conn_text");
        const toggle = $("log_toggle_btn");

        function setState(state) {
            dot.className = "cs_" + state;
            dot.style.background = state === "on" ? "#34c76a"
                : (state === "off" ? "#e05252" : "#808080");
            if (state === "on") {
                text.textContent = "已连接";
                toggle.textContent = "断开";
            } else if (state === "off") {
                text.textContent = "未连接";
                toggle.textContent = "连接";
            } else {
                text.textContent = "检测中";
                toggle.textContent = "连接";
            }
            const st = $("conn_state");
            if (st) st.textContent = text.textContent;
        }

        async function poll() {
            try {
                const resp = await fetch("/api/vnc/status");
                if (!resp.ok) return setState("unknown");
                const data = await resp.json();
                setState(data.connected ? "on" : "off");
            } catch (err) {
                setState("unknown");
            }
        }

        function forceConnect(ui) {
            if (ui.rfb === undefined) {
                try { ui.connect(); } catch (err) { /* 忽略 */ }
                return;
            }
            try { ui.disconnect(); } catch (err) { /* 忽略 */ }
            const t0 = Date.now();
            const iv = setInterval(() => {
                const gone = ui.rfb === undefined || Date.now() - t0 > 3000;
                if (!gone) return;
                clearInterval(iv);
                if (ui.rfb !== undefined) {
                    try { ui.rfb = undefined; } catch (err) { /* 忽略 */ }
                }
                try { ui.connect(); } catch (err) { /* 忽略 */ }
            }, 120);
        }

        function init() {
            toggle.addEventListener("click", async () => {
                const ui = window.UI;
                const isActive = dot.className === "cs_on" ||
                    (ui && ui.rfb !== undefined && ui.connected);
                if (isActive) {
                    try {
                        await fetch("/api/vnc/disconnect", { method: "POST" });
                    } catch (err) { /* 忽略 */ }
                    if (ui && ui.disconnect) {
                        try { ui.disconnect(); } catch (err) { /* 忽略 */ }
                    }
                } else if (ui) {
                    forceConnect(ui);
                }
                poll();
            });
            poll();
            setInterval(poll, 1000);
        }

        return { init };
    })();

    /* ===== 启动 ===== */
    function hideLoading() {
        const mask = $("app_loading_mask");
        if (mask) mask.style.display = "none";
    }

    function setupEncoder() {
        const btns = document.querySelectorAll(".enc_btn");
        if (!btns.length) return;
        const t = () => theme.palette();
        function highlight(name) {
            btns.forEach((b) => {
                const on = b.dataset.enc === name;
                if (on) {
                    b.style.background = t().navactive;
                    b.style.borderColor = t().navactiveborder;
                    b.style.color = "#ffffff";
                } else {
                    b.style.background = t().panel;
                    b.style.borderColor = t().input;
                    b.style.color = t().fg;
                }
            });
        }
        btns.forEach((b) => {
            b.addEventListener("click", async () => {
                const enc = b.dataset.enc;
                currentEncoder = enc;
                highlight(enc);
                try {
                    await fetch("/api/encoder", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ encoder: enc }),
                    });
                } catch (err) { /* 忽略 */ }
            });
        });
        document.addEventListener("wv-theme-change", () => {
            const active = document.querySelector(".enc_btn.active");
            if (active) highlight(active.dataset.enc);
        });
        fetch("/api/encoder")
            .then((r) => (r.ok ? r.json() : null))
            .then((d) => {
                if (d && d.encoder) {
                    currentEncoder = d.encoder;
                    const b = document.querySelector(
                        '.enc_btn[data-enc="' + d.encoder + '"]');
                    if (b) {
                        b.classList.add("active");
                        highlight(d.encoder);
                    }
                }
            })
            .catch(() => { /* 忽略 */ });
    }

    let currentEncoder = "zlib";  // 当前传输编码（性能面板显示用）

    const perf = (function () {
        const overlay = $("perf_overlay");
        const toggle = $("perf_show_btn");
        let enabled = false;
        let frames = 0;
        let lastCount = 0;
        let fps = 0;
        let latency = -1;
        let reso = "--";
        let encoder = "-";
        let hooked = false;
        let timers = null;

        function hookRfb() {
            const rfb = (window.UI || {}).rfb;
            if (!rfb || hooked || typeof rfb._framebufferUpdate !== "function") {
                return;
            }
            hooked = true;
            const orig = rfb._framebufferUpdate.bind(rfb);
            rfb._framebufferUpdate = function () {
                frames++;
                return orig.apply(rfb, arguments);
            };
        }

        function ping() {
            const t0 = performance.now();
            fetch("/api/ping", { cache: "no-store" })
                .then(() => { latency = Math.round(performance.now() - t0); })
                .catch(() => { latency = -1; });
        }

        function tick() {
            if (!enabled || !overlay) return;
            hookRfb();
            const rfb = (window.UI || {}).rfb;
            if (rfb) {
                const w = rfb._fbWidth, h = rfb._fbHeight;
                if (w && h) reso = w + "x" + h;
                else if (rfb._display && rfb._display.get_width) {
                    reso = rfb._display.get_width() + "x" + rfb._display.get_height();
                }
            }
            encoder = currentEncoder;
            const now = performance.now();
            if (now - lastCount >= 1000) {
                fps = Math.round(frames * 1000 / (now - lastCount));
                lastCount = now;
                frames = 0;
            }
            overlay.textContent = "帧率: " + (fps > 0 ? fps : "--") + " FPS\n画质: " +
                reso + " / " + encoder.toUpperCase() + "\n延迟: " +
                (latency >= 0 ? latency : "--") + " ms";
        }

        function init() {
            if (!overlay || !toggle) return;
            toggle.addEventListener("change", () => {
                enabled = toggle.checked;
                overlay.style.display = enabled ? "block" : "none";
                if (enabled) {
                    frames = 0;
                    lastCount = performance.now();
                    fps = 0;
                    latency = -1;
                    reso = "--";
                    hookRfb();
                    ping();
                    tick();
                    if (!timers) {
                        timers = [
                            setInterval(tick, 500),
                            setInterval(ping, 2000),
                        ];
                    }
                }
            });
        }

        return { init };
    })();

    function setupClipboard() {
        const btn = $("noVNC_send_clipboard_button");
        if (!btn) return;
        btn.addEventListener("click", async () => {
            const ui = window.UI;
            const ta = $("noVNC_clipboard_text");
            const text = ta.value;
            if (text === "") return;
            try {
                await fetch("/api/clipboard", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text }),
                });
            } catch (err) { /* 忽略 */ }
            if (ui && ui.rfb) {
                try {
                    ui.rfb.clipboardPasteFrom(text);
                } catch (err) { /* 忽略 */ }
            }
        });
    }

    function boot() {
        setupQ3Nav();
        setupScreenTools();
        onscreenKeyboard.init();
        setupZoom();
        setupConnPane();
        theme.init();
        moveDialog.init();
        fm.init();
        term.init();
        srvlog.init();
        portPanel.init();
        connStatus.init();
        setupClipboard();
        perf.init();
        setupEncoder();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
