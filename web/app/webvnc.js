/* webvnc 主界面脚本：
   分割条拖拽 + 文件树（行内按钮/拖拽上传）+ 移动弹窗 + 命令行
   + 服务端日志 + 三象限分类切换 + 主题 + 屏幕浮动按钮 */
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);

    /* ====================================================================
     * 分割条拖拽（双击复位）
     * ================================================================== */
    function setupDividers() {
        const root = document.documentElement;

        function onDrag(el, onMove) {
            let dragging = false;
            el.addEventListener("pointerdown", (ev) => {
                dragging = true;
                el.setPointerCapture(ev.pointerId);
                ev.preventDefault();
            });
            el.addEventListener("pointermove", (ev) => {
                if (!dragging) return;
                onMove(ev);
                if (!onDrag._t) {
                    onDrag._t = setTimeout(() => {
                        onDrag._t = null;
                        window.dispatchEvent(new Event("resize"));
                    }, 100);
                }
            });
            const stop = () => {
                if (!dragging) return;
                dragging = false;
                window.dispatchEvent(new Event("resize"));
            };
            el.addEventListener("pointerup", stop);
            el.addEventListener("pointercancel", stop);
            el.addEventListener("dblclick", () => {
                root.style.removeProperty("--wv-left-w");
                root.style.removeProperty("--wv-bottom-h");
                window.dispatchEvent(new Event("resize"));
            });
        }

        const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

        onDrag($("div_v"), (ev) => {
            const w = clamp(ev.clientX - 3, 160, window.innerWidth * 0.6);
            root.style.setProperty("--wv-left-w", w + "px");
        });
        onDrag($("div_h"), (ev) => {
            const h = clamp(window.innerHeight - ev.clientY - 3,
                            100, window.innerHeight * 0.75);
            root.style.setProperty("--wv-bottom-h", h + "px");
        });
    }

    /* ====================================================================
     * 三象限：左栏分类切换
     * ================================================================== */
    function setupQ3Nav() {
        const btns = document.querySelectorAll(".q3_nav_btn");
        const panes = document.querySelectorAll(".q3_pane");
        btns.forEach((btn) => {
            btn.addEventListener("click", () => {
                btns.forEach((b) => b.classList.toggle("active", b === btn));
                panes.forEach((p) => p.classList.toggle(
                    "active", p.dataset.pane === btn.dataset.pane));
            });
        });
    }

    /* ====================================================================
     * 一象限：屏幕浮动按钮（网页全屏 / 全屏网页，右下角）
     * ================================================================== */
    function setupScreenTools() {
        // 网页全屏：整个网页进入浏览器原生全屏
        $("st_page_fs_btn").addEventListener("click", () => {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.documentElement.requestFullscreen()
                    .catch(() => {});
            }
        });

        // 全屏网页：屏幕区铺满浏览器窗口（隐藏其他象限）
        const layout = $("webvnc_layout");
        $("st_full_page_btn").addEventListener("click", () => {
            const on = layout.classList.toggle("screen_fs");
            $("st_full_page_btn").textContent = on ? "退出全屏" : "全屏网页";
            window.dispatchEvent(new Event("resize"));
        });
    }

    /* ====================================================================
     * 三象限：缩放调整（原始 / 适配 / 远程）
     * ================================================================== */
    function setupZoom() {
        const sel = $("noVNC_setting_resize");
        const btns = document.querySelectorAll(".zoom_btn");

        function sync() {
            btns.forEach((b) => b.classList.toggle("active",
                                                   b.dataset.mode === sel.value));
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
     * 主题（三象限"设置"分类）：背景 / 文字 / 选中 / 强调 + 字体 / 字号
     * 持久化到 localStorage，默认 noVNC 深色配色
     * ================================================================== */
    const theme = (function () {
        const STORE = "wv_theme_v1";
        const DEFAULTS = {
            bg: "#494949", fg: "#eeeeee", sel: "#5d5d5d",
            accent: "#8a8a8a", font: "", size: 13,
        };

        function contrastOn(hex) {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return (0.299 * r + 0.587 * g + 0.114 * b) > 140
                ? "#000000" : "#ffffff";
        }

        function apply(t) {
            const root = document.documentElement.style;
            root.setProperty("--wv-bg", t.bg);
            root.setProperty("--wv-fg", t.fg);
            root.setProperty("--wv-sel", t.sel);
            root.setProperty("--wv-accent", t.accent);
            root.setProperty("--wv-accent-fg", contrastOn(t.accent));
            root.setProperty("--wv-size", t.size + "px");
            if (t.font) root.setProperty("--wv-font", t.font);
        }

        function load() {
            try {
                const raw = localStorage.getItem(STORE);
                if (raw) return Object.assign({}, DEFAULTS, JSON.parse(raw));
            } catch (err) { /* 忽略损坏数据 */ }
            return Object.assign({}, DEFAULTS);
        }

        function save(t) {
            try { localStorage.setItem(STORE, JSON.stringify(t)); }
            catch (err) { /* 存储不可用 */ }
        }

        function init() {
            const ctrl = {
                bg: $("th_bg"), fg: $("th_fg"), sel: $("th_sel"),
                accent: $("th_accent"), font: $("th_font"),
                size: $("th_size"), reset: $("th_reset_btn"),
            };
            if (!ctrl.bg) return;
            let t = load();
            apply(t);
            ctrl.bg.value = t.bg;
            ctrl.fg.value = t.fg;
            ctrl.sel.value = t.sel;
            ctrl.accent.value = t.accent;
            ctrl.font.value = t.font || "";
            ctrl.size.value = t.size;

            const update = () => {
                t = {
                    bg: ctrl.bg.value, fg: ctrl.fg.value,
                    sel: ctrl.sel.value, accent: ctrl.accent.value,
                    font: ctrl.font.value,
                    size: parseInt(ctrl.size.value, 10) || 13,
                };
                apply(t);
                save(t);
            };
            ctrl.bg.addEventListener("input", update);
            ctrl.fg.addEventListener("input", update);
            ctrl.sel.addEventListener("input", update);
            ctrl.accent.addEventListener("input", update);
            ctrl.font.addEventListener("change", update);
            ctrl.size.addEventListener("change", update);
            ctrl.reset.addEventListener("click", () => {
                t = Object.assign({}, DEFAULTS);
                ctrl.bg.value = t.bg;
                ctrl.fg.value = t.fg;
                ctrl.sel.value = t.sel;
                ctrl.accent.value = t.accent;
                ctrl.font.value = t.font || "";
                ctrl.size.value = t.size;
                apply(t);
                save(t);
            });
        }

        return { init };
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
            const b = document.createElement("button");
            b.className = "row_btn" + (cls ? " " + cls : "");
            b.textContent = text;
            b.title = title;
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
            /* 删除 → 点击后变 "确认" 要求再次确认，再点执行删除 */
            return rowButton("删除", "删除（点击两次确认）", "danger", (btn) => {
                if (btn.classList.contains("confirm")) {
                    clearTimeout(confirmTimer);
                    doDelete(p);
                    return;
                }
                btn.classList.add("confirm");
                btn.textContent = "确认";
                confirmTimer = setTimeout(() => {
                    btn.classList.remove("confirm");
                    btn.textContent = "删除";
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

        /* ---- 渲染 ---- */
        function render() {
            pathText.textContent = state.path || "(根目录)";
            updateNav();
            tree.innerHTML = "";
            if (state.items.length === 0) {
                const empty = document.createElement("div");
                empty.className = "fm_item";
                empty.style.color = "#888";
                empty.textContent = "(空目录)";
                tree.appendChild(empty);
            }
            for (const item of state.items) {
                const row = document.createElement("div");
                row.className = "fm_item" + (item.is_dir ? " dir" : " file");
                row.dataset.name = item.name;
                const p = joinPath(state.path, item.name);

                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.className = "fm_check";
                cb.checked = state.selected.has(item.name);
                cb.addEventListener("click", (ev) => ev.stopPropagation());
                cb.addEventListener("change", () => {
                    if (cb.checked) state.selected.add(item.name);
                    else state.selected.delete(item.name);
                });

                const icon = document.createElement("span");
                icon.className = "fm_icon";
                icon.textContent = item.is_dir ? "\u25A3" : "\u25A2";

                const name = document.createElement("span");
                name.className = "fm_name";
                name.textContent = item.name + (item.is_dir ? "/" : "");

                const btns = document.createElement("span");
                btns.className = "row_btns";
                if (item.is_dir) {
                    btns.appendChild(rowButton("zip下载", "打包 zip 下载", "", () => {
                        zipDownload([p]);
                    }));
                } else {
                    btns.appendChild(rowButton("下载", "下载文件", "", () => {
                        downloadPath(p);
                    }));
                }
                btns.appendChild(rowButton("重命名", "重命名", "", () => renameItem(p)));
                btns.appendChild(rowButton("移动", "移动到目录", "", () => moveItems([p])));
                btns.appendChild(deleteButton(p));

                const size = document.createElement("span");
                size.className = "fm_size";
                size.textContent = item.is_dir ? "" : fmtSize(item.size);

                row.appendChild(cb);
                row.appendChild(icon);
                row.appendChild(name);
                row.appendChild(btns);
                row.appendChild(size);

                row.addEventListener("click", (ev) => {
                    const mult = ev.ctrlKey || ev.metaKey || ev.shiftKey;
                    if (!mult) {
                        for (const r of tree.children) {
                            if (r !== row) r.classList.remove("selected");
                        }
                        state.selected.clear();
                        row.querySelector(".fm_check").checked = true;
                        state.selected.add(item.name);
                    } else {
                        cb.checked = !cb.checked;
                        if (cb.checked) state.selected.add(item.name);
                        else state.selected.delete(item.name);
                    }
                    row.classList.add("selected");
                });
                row.addEventListener("dblclick", () => {
                    if (item.is_dir) {
                        state.selected.clear();
                        load(joinPath(state.path, item.name));
                    } else {
                        downloadPath(joinPath(state.path, item.name));
                    }
                });
                tree.appendChild(row);
            }
            setStatus(state.items.length + " 项" +
                      (state.selected.size ? "，已选 " + state.selected.size : ""));
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
            setupDragDrop();
            showRoot();
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
            $("mv_path_text").textContent = mv.path || "(根目录)";
            $("mv_up_btn").disabled = !mv.parent;
            treeEl.innerHTML = "";
            if (mv.items.length === 0) {
                const empty = document.createElement("div");
                empty.className = "mv_item";
                empty.style.color = "#888";
                empty.textContent = "(无子目录)";
                treeEl.appendChild(empty);
            }
            for (const item of mv.items) {
                if (!item.is_dir) continue;
                const row = document.createElement("div");
                row.className = "mv_item";
                const icon = document.createElement("span");
                icon.textContent = "\u25A3";
                const name = document.createElement("span");
                name.textContent = item.name + "/";
                row.appendChild(icon);
                row.appendChild(name);
                const p = mv.path ? mv.path.replace(/[\/\\]$/, "") + "/" + item.name
                                  : item.name;
                row.addEventListener("click", () => {
                    treeEl.querySelectorAll(".mv_item")
                        .forEach((r) => r.classList.remove("selected"));
                    row.classList.add("selected");
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
            mask.classList.add("show");
            dlg.classList.add("show");
            showRoot();
        }

        function close() {
            mask.classList.remove("show");
            dlg.classList.remove("show");
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
            const div = document.createElement("div");
            div.className = cls;
            div.textContent = text;
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
                await pollJob(data.job);
            } catch (err) {
                appendLine("term_out", "[请求失败] " + err);
            } finally {
                currentJob = null;
                $("term_send_btn").disabled = false;
                $("term_stop_btn").disabled = true;
            }
        }

        async function init() {
            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") { ev.preventDefault(); execute(); }
            });
            $("term_send_btn").addEventListener("click", execute);
            $("term_stop_btn").addEventListener("click", stopJob);
            $("term_clear_btn").addEventListener("click", () => {
                output.innerHTML = "";
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
        }

        return { init };
    })();

    /* ====================================================================
     * 四象限：服务端日志（轮询 /api/log/tail）
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

        function init() {
            $("log_clear_btn").addEventListener("click", () => {
                output.innerHTML = "";
            });
            poll();
            timer = setInterval(poll, 2000);
        }

        return { init };
    })();

    /* ====================================================================
     * 服务端日志标题栏：VNC 连接状态 + 连接/断开按钮（互转）
     * ================================================================== */
    const connStatus = (function () {
        const dot = $("log_conn_dot");
        const text = $("log_conn_text");
        const toggle = $("log_toggle_btn");

        function setState(state) {
            dot.className = "cs_" + state;
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

        function init() {
            toggle.addEventListener("click", async () => {
                const on = dot.className === "cs_on";
                if (on) {
                    try {
                        await fetch("/api/vnc/disconnect", { method: "POST" });
                    } catch (err) { /* 忽略 */ }
                    if (window.UI && window.UI.disconnect) {
                        try { window.UI.disconnect(); } catch (err) { /* 忽略 */ }
                    }
                } else if (window.UI && window.UI.connect) {
                    const ui = window.UI;
                    if (ui.rfb !== undefined && !ui.connected) {
                        try { ui.disconnect(); } catch (err) { /* 忽略 */ }
                        setTimeout(() => { try { ui.connect(); } catch (err) { /* 忽略 */ } }, 500);
                    } else {
                        try { ui.connect(); } catch (err) { /* 忽略 */ }
                    }
                }
                poll();
            });
            poll();
            setInterval(poll, 1000);
        }

        return { init };
    })();

    /* ===== 启动 ===== */
    function boot() {
        setupDividers();
        setupQ3Nav();
        setupScreenTools();
        setupZoom();
        theme.init();
        moveDialog.init();
        fm.init();
        term.init();
        srvlog.init();
        connStatus.init();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
