/* webvnc 底部命令行终端 */
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const output = $("term_output");
    const input = $("term_input");

    function esc(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function appendLine(cls, text) {
        const div = document.createElement("div");
        div.className = cls;
        div.textContent = text;
        output.appendChild(div);
        output.scrollTop = output.scrollHeight;
    }

    async function execute() {
        const command = input.value.trim();
        if (!command) return;
        input.value = "";
        appendLine("term_prompt", "\u25B6 " + command);
        try {
            const resp = await fetch("/api/cmd", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command: command, timeout: 300 }),
            });
            const data = await resp.json();
            let text = data.output || "";
            if (text === "") text = "(无输出)";
            appendLine("term_out", text);
            if (typeof data.exit_code === "number") {
                appendLine("term_prompt", "\u23CE 退出码: " + data.exit_code);
            }
        } catch (err) {
            appendLine("term_out", "[请求失败] " + err);
        }
    }

    function bind() {
        input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") {
                ev.preventDefault();
                execute();
            }
        });
        $("term_send_btn").addEventListener("click", execute);
        $("term_clear_btn").addEventListener("click", () => {
            output.innerHTML = "";
        });
        $("term_close_btn").addEventListener("click", () => $("term_panel").classList.add("hidden"));
    }

    async function init() {
        bind();
        try {
            const resp = await fetch("/api/info");
            const info = await resp.json();
            let head = "webvnc " + info.platform + " / Python " + info.python;
            if (info.windows) head += " / Windows 屏幕共享已启用";
            else head += " / 虚拟屏幕演示模式";
            if (info.hostname) head += " / " + info.hostname;
            appendLine("term_prompt", head);
            appendLine("term_prompt", "输入命令并按 Enter 执行 (Windows: cmd, 其它: sh)");
        } catch (err) {
            appendLine("term_out", "[初始化失败] " + err);
        }
        input.focus();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
