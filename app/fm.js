/* webvnc 左侧文件管理器 */
(function () {
    "use strict";

    const state = {
        path: "",
        items: [],
        selected: new Set(),
        drives: [],
    };

    const $ = (id) => document.getElementById(id);
    const tree = $("fm_tree");
    const pathBar = $("fm_path");
    const status = $("fm_status");

    function fmtSize(n) {
        if (n < 1024) return n + " B";
        const units = ["KB", "MB", "GB", "TB"];
        let v = n;
        let u = -1;
        do {
            v /= 1024;
            u += 1;
        } while (v >= 1024 && u < units.length - 1);
        return v.toFixed(1) + " " + units[u];
    }

    function fmtTime(ts) {
        if (!ts) return "";
        const d = new Date(ts * 1000);
        return d.toLocaleString();
    }

    async function api(url, opts) {
        const resp = await fetch(url, opts);
        const ct = resp.headers.get("Content-Type") || "";
        if (ct.includes("application/json")) {
            return await resp.json();
        }
        return resp;
    }

    function setStatus(msg) {
        status.textContent = msg;
    }

    function iconOf(item) {
        return item.is_dir ? "\u25A3" : "\u25A2";
    }

    function render() {
        pathBar.textContent = state.path || "(根)";
        tree.innerHTML = "";
        if (state.items.length === 0) {
            const empty = document.createElement("div");
            empty.className = "fm_item";
            empty.style.color = "#777";
            empty.textContent = "(空目录)";
            tree.appendChild(empty);
        }
        for (const item of state.items) {
            const row = document.createElement("div");
            row.className = "fm_item" + (item.is_dir ? " dir" : " file");
            row.dataset.name = item.name;

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
            icon.textContent = iconOf(item);

            const name = document.createElement("span");
            name.className = "fm_name";
            name.textContent = item.name + (item.is_dir ? "/" : "");

            const size = document.createElement("span");
            size.className = "fm_size";
            size.textContent = item.is_dir ? "" : fmtSize(item.size);

            row.appendChild(cb);
            row.appendChild(icon);
            row.appendChild(name);
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
                    const a = document.createElement("a");
                    a.href = "/api/fs/download?path=" + encodeURIComponent(joinPath(state.path, item.name));
                    a.download = "";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }
            });
            tree.appendChild(row);
        }
        setStatus(state.items.length + " 项" +
                  (state.selected.size ? "，已选 " + state.selected.size : ""));
    }

    function joinPath(dir, name) {
        if (!dir) return name;
        if (dir.endsWith("/") || dir.endsWith("\\")) return dir + name;
        return dir + "/" + name;
    }

    function normalizePath(p) {
        return p.replace(/\\/g, "/").replace(/\/+/g, "/").replace(/\/$/, "") || "/";
    }

    async function load(path) {
        try {
            const res = await api("/api/fs/list?path=" + encodeURIComponent(path || ""));
            if (res.error) {
                setStatus("错误: " + res.error);
                return;
            }
            state.path = res.path || path;
            state.items = res.items || [];
            state.selected.clear();
            render();
        } catch (err) {
            setStatus("请求失败: " + err);
        }
    }

    function currentPaths() {
        const names = Array.from(state.selected);
        return names.map((n) => joinPath(state.path, n));
    }

    async function refresh() {
        await load(state.path);
    }

    async function goUp() {
        if (state.path === "") return;
        const res = await api("/api/fs/list?path=" + encodeURIComponent(state.path));
        if (res.parent) {
            await load(res.parent);
        } else {
            await showDrives();
        }
    }

    async function showDrives() {
        try {
            const res = await api("/api/fs/drives");
            state.drives = res.drives || [];
            state.path = "";
            state.items = state.drives.map((d) => ({
                name: d,
                is_dir: true,
                size: 0,
                mtime: 0,
            }));
            state.selected.clear();
            render();
            pathBar.textContent = "(驱动器)";
        } catch (err) {
            setStatus("加载驱动器失败: " + err);
        }
    }

    function selectedPaths() {
        const paths = currentPaths();
        if (paths.length === 0) {
            setStatus("请先选择文件或文件夹");
            return null;
        }
        return paths;
    }

    function doUpload() {
        const input = $("fm_file_input");
        input.value = "";
        input.click();
    }

    async function onFilesChosen() {
        const input = $("fm_file_input");
        if (!input.files.length) return;
        const fd = new FormData();
        for (const f of input.files) fd.append("file", f);
        setStatus("上传中...");
        try {
            const res = await api("/api/fs/upload?path=" + encodeURIComponent(state.path), {
                method: "POST",
                body: fd,
            });
            setStatus(res.error ? ("上传失败: " + res.error) : ("已上传: " + (res.saved || []).join(", ")));
            await refresh();
        } catch (err) {
            setStatus("上传失败: " + err);
        }
    }

    async function doMkdir() {
        const name = prompt("新建文件夹名称:");
        if (!name) return;
        const target = joinPath(state.path, name);
        setStatus("创建中...");
        try {
            const res = await api("/api/fs/mkdir", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: target }),
            });
            setStatus(res.ok ? "已创建" : ("失败: " + res.error));
            await refresh();
        } catch (err) {
            setStatus("失败: " + err);
        }
    }

    async function doDownload() {
        const paths = selectedPaths();
        if (!paths) return;
        for (const p of paths) {
            const a = document.createElement("a");
            a.href = "/api/fs/download?path=" + encodeURIComponent(p);
            a.download = "";
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
    }

    async function doRename() {
        const paths = selectedPaths();
        if (!paths) return;
        if (paths.length > 1) {
            setStatus("一次只能重命名一个项目");
            return;
        }
        const oldName = paths[0].split(/[\\/]/).pop();
        const newName = prompt("新名称:", oldName);
        if (!newName || newName === oldName) return;
        try {
            const res = await api("/api/fs/rename", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: paths[0], new_name: newName }),
            });
            setStatus(res.ok ? "已重命名" : ("失败: " + res.error));
            await refresh();
        } catch (err) {
            setStatus("失败: " + err);
        }
    }

    async function doMove() {
        const paths = selectedPaths();
        if (!paths) return;
        const dest = prompt("移动到目录 (输入目标路径):", state.path);
        if (!dest) return;
        try {
            const res = await api("/api/fs/move", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ paths: paths, dest: dest }),
            });
            setStatus(res.ok ? "已移动 " + res.moved.length + " 项" : ("失败: " + res.error));
            await refresh();
        } catch (err) {
            setStatus("失败: " + err);
        }
    }

    async function doZip() {
        const paths = selectedPaths();
        if (!paths) return;
        setStatus("打包中...");
        const query = paths.map((p) => encodeURIComponent(p)).join(",");
        const a = document.createElement("a");
        a.href = "/api/fs/zip?paths=" + query;
        a.download = "webvnc.zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setStatus("已开始下载 zip");
    }

    function bind() {
        $("fm_refresh_btn").addEventListener("click", refresh);
        $("fm_up_btn").addEventListener("click", goUp);
        $("fm_drives_btn").addEventListener("click", showDrives);
        $("fm_upload_btn").addEventListener("click", doUpload);
        $("fm_mkdir_btn").addEventListener("click", doMkdir);
        $("fm_download_btn").addEventListener("click", doDownload);
        $("fm_rename_btn").addEventListener("click", doRename);
        $("fm_move_btn").addEventListener("click", doMove);
        $("fm_zip_btn").addEventListener("click", doZip);
        $("fm_file_input").addEventListener("change", onFilesChosen);
        $("fm_close_btn").addEventListener("click", () => $("file_panel").classList.add("hidden"));
    }

    function init() {
        bind();
        showDrives();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
