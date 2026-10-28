"""Full-screen chat interface for hyperRouter."""

from __future__ import annotations

import re
import sys
from typing import Any

from hyperrouter_lib.quickopen import TuiQuickOpenMixin

TUI_HELP = [
    ("Enter", "send the message"),
    ("Ctrl+P", "pick a free model"),
    ("Ctrl+O", "usage for this machine"),
    ("Ctrl+U", "clear the input line"),
    ("Ctrl+S", "settings browser (search, edit, save)"),
    ("F2", "settings browser (same as Ctrl+S)"),
    ("Ctrl+K", "start a new conversation"),
    ("Ctrl+C", "cancel a running request"),
    ("Ctrl+R", "retry the last message"),
    ("Ctrl+F", "filter the transcript (/find)"),
    ("Ctrl+D", "quit"),
    ("PgUp/PgDn", "scroll the transcript"),
    ("Up/Down", "scroll, or browse input history"),
    ("Ctrl+L", "redraw"),
    ("Mouse", "wheel scrolls; click a hint or overlay row"),
    ("y / n / a", "answer an approval after reading its diff"),
    ("Tab", "complete an @file path"),
    ("F1 or ?", "this help"),
    ("", ""),
    ("/model", "switch model or alias"),
    ("/models", "rank free models for a task"),
    ("/task", "pin the task type"),
    ("/agent", "opencode / dsh / freebuff / off"),
    ("/tools", "turn the coding tools on or off"),
    ("/todos", "show the agent's task list"),
    ("/workers", "parallel workers: state and changed files"),
    ("/image", "attach an image to the next message"),
    ("/plan", "read-only mode: propose, do not edit"),
    ("/undo-edit", "restore the last edited file from backup"),
    ("/skill", "load a session skill"),
    ("/skills", "list installed skills"),
    ("/mcp", "MCP servers and tools"),
    ("/usage", "usage report"),
    ("/settings", "settings browser (same as Ctrl+S)"),
    ("/compact", "summarize the conversation"),
    ("/export", "save the conversation as markdown"),
    ("/session", "show the session file"),
    ("/retry", "resend the last user message"),
    ("/find", "filter the transcript; no argument clears it"),
    ("/keys", "keyboard shortcuts"),
    ("/clear", "forget the conversation"),
]


class TuiApp(TuiQuickOpenMixin):
    """Full-screen chat: transcript pane, input line, model picker, overlays."""

    def __getattribute__(self, name: str) -> Any:
        if name != "_bind_cli_globals":
            object.__getattribute__(self, "_bind_cli_globals")()
        return super().__getattribute__(name)

    @staticmethod
    def _bind_cli_globals() -> None:
        cli = sys.modules.get("hyperrouter") or sys.modules.get("hyperrouter_cli")
        if cli is None:
            harness = sys.modules.get("tests.harness") or sys.modules.get("harness")
            cli = getattr(harness, "hr", None) if harness is not None else None
        if cli is not None:
            globals().update({key: value for key, value in vars(cli).items()
                              if not key.startswith("__")})

    def __init__(self, screen: Any, args: argparse.Namespace, curses_mod: Any):
        self._bind_cli_globals()
        self.s = screen
        self.c = curses_mod
        self.args = args
        self.config = load_config()
        ccfg = self.config.get("chat") or {}
        self.model = args.model or str(ccfg.get("model") or "auto")
        self.task = args.task or ""
        self.strategy = args.strategy or ccfg.get("strategy") or None
        self.temperature = (args.temperature if args.temperature is not None
                            else float(ccfg.get("temperature") if ccfg.get("temperature") is not None else 0.7))
        self.max_tokens = (args.max_tokens if args.max_tokens is not None
                           else int(ccfg.get("max_tokens") or 0))
        self.stream = bool(ccfg.get("stream", True)) and not getattr(args, "no_stream", False)
        self.enrich = bool(ccfg.get("auto_enrich")) or bool(getattr(args, "enrich", False))
        self.persona = args.persona or ccfg.get("persona")
        self.system_extra = (args.system if getattr(args, "system", None) is not None
                             else str(ccfg.get("system") or ""))
        self.skill_names = [str(x) for x in (getattr(args, "skill", None) or [])]
        self.skill_names += [str(x) for x in (ccfg.get("skills") or [])]
        self.skill_names += [name for name in project_skills() if name not in self.skill_names]
        self.agent_backend = getattr(args, "agent", None) or None
        self.show_tokens = bool(ccfg.get("show_token_usage", True))
        self.history_limit = max(2, int(ccfg.get("history_limit") or 40))
        acfg = self.config.get("agent") or {}
        self.tools_enabled = bool(acfg.get("enabled", True)) and not getattr(args, "no_tools", False)
        self.auto_approve = bool(acfg.get("auto_approve")) or bool(getattr(args, "auto", False))
        self.allow_outside = bool(acfg.get("allow_outside"))
        self.max_rounds = max(1, int(acfg.get("max_rounds") or 8))
        self.subagents = bool(acfg.get("subagents", True)) and not getattr(args, "no_subagents", False)
        self.web_tools = bool((self.config.get("mcp") or {}).get("agent", True))
        self.max_subagents = int(acfg.get("max_subagents") or 4)
        self.subagent_rounds = int(acfg.get("subagent_rounds") or 4)
        self.todos: list[dict[str, Any]] = []
        self.workers: dict[int, dict[str, Any]] = {}
        self.approval: dict[str, Any] | None = None
        self.approval_lock = threading.Lock()
        self.session = chat_session_path(args, self.config) or sessions_dir() / "default.json"
        self.transcript = None
        if ccfg.get("save_transcript", True) and not getattr(args, "no_save", False):
            self.transcript = transcript_dir(self.config) / (
                f"tui-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl")
        self.messages: list[dict[str, Any]] = []
        self._load_session()
        self.buffer = ""
        self.pending_images: list[dict[str, Any]] = []
        self.plan_mode = False
        self.file_matches: list[str] = []
        self.file_match_index = 0
        self.file_index: list[str] | None = None
        self.file_index_at = 0.0
        self.filter = ""
        self.lines_cache: tuple[Any, list[tuple[str, int]]] | None = None
        self.stream_cache: tuple[Any, list[str]] | None = None
        self.click_targets: list[tuple[int, int, int, tuple[str, Any]]] = []
        self.ctx_tokens = 0
        self.ctx_cache: tuple[Any, int] | None = None
        self.stream_started = 0.0
        self.first_chunk = 0.0
        self.history: list[str] = []
        self.history_index = 0
        self.scroll = 0
        self.busy = False
        self.cancel = threading.Event()
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.overlay: dict[str, Any] | None = None
        self.stream_buf = ""
        self.notice = ""
        self.notice_until = 0.0
        self.quitting = False
        self.spinner = 0
        self.pairs: dict[str, int] = {}
        self.settings_cache: list[dict[str, Any]] | None = None
        self.settings_sections: list[str] = []
        self._model_items_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._term_attrs: tuple[int, Any] | None = None
        self._setup_screen()

    # -- setup ------------------------------------------------------------

    def _setup_screen(self) -> None:
        # Ctrl+S is XOFF in a normal terminal: without this the key is swallowed
        # by the tty line discipline and the screen freezes instead of opening
        # the settings overlay. Turn software flow control off for this session.
        try:
            import termios
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
            self._term_attrs = (fd, attrs)
            raw = list(attrs)
            raw[0] &= ~(termios.IXON | termios.IXOFF)
            termios.tcsetattr(fd, termios.TCSADRAIN, raw)
        except (ImportError, AttributeError, OSError, ValueError):
            self._term_attrs = None
        try:
            self.c.curs_set(1)
        except self.c.error:
            pass
        self.s.keypad(True)
        self.s.timeout(40)
        try:
            self.c.mousemask(self.c.ALL_MOUSE_EVENTS)
        except (self.c.error, AttributeError):
            pass
        try:
            self.c.start_color()
            self.c.use_default_colors()
            for index, color in enumerate((self.c.COLOR_CYAN, self.c.COLOR_GREEN,
                                           self.c.COLOR_YELLOW, self.c.COLOR_RED,
                                           self.c.COLOR_MAGENTA, self.c.COLOR_BLUE), 1):
                self.c.init_pair(index, color, -1)
            self.pairs = {"cyan": 1, "green": 2, "yellow": 3, "red": 4,
                          "magenta": 5, "blue": 6}
        except self.c.error:
            self.pairs = {}
        try:
            self.c.curs_set(1)
        except self.c.error:
            pass

    def _attr(self, name: str, extra: int = 0) -> int:
        pair = self.pairs.get(name)
        base = self.c.color_pair(pair) if pair else 0
        return base | extra

    # -- session ----------------------------------------------------------

    def _load_session(self) -> None:
        if not self.session or not self.session.is_file():
            return
        try:
            saved = json.loads(self.session.read_text(encoding="utf-8"))
            loaded = saved.get("messages") if isinstance(saved, dict) else saved
            if isinstance(loaded, list):
                self.messages = [m for m in loaded if isinstance(m, dict)
                                 and m.get("role") in {"user", "assistant", "info"}]
                if isinstance(saved, dict) and saved.get("model"):
                    self.model = str(saved["model"])
        except (OSError, json.JSONDecodeError):
            pass

    def _persist(self) -> None:
        if not self.session:
            return
        try:
            self.session.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.session.write_text(json.dumps(
                {"version": 1, "model": self.model, "messages": self.messages},
                indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass

    def _transcript(self, role: str, content: str, meta: dict[str, Any] | None = None) -> None:
        if self.transcript is None:
            return
        transcript_append(self.transcript, {"ts": utc_now(), "role": role,
                                            "content": content, "model": self.model,
                                            "meta": meta or {}})

    # -- drawing ----------------------------------------------------------

    def _add(self, row: int, col: int, text: str, attr: int = 0) -> None:
        try:
            height, width = self.s.getmaxyx()
            if row < 0 or row >= height or col < 0 or col >= width:
                return
            self.s.addstr(row, col, clip_display(text, width - col), attr)
        except self.c.error:
            pass

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        width = max(8, width)
        out: list[str] = []
        for raw in (text or "").splitlines() or [""]:
            if not raw.strip():
                out.append("")
                continue
            out.extend(textwrap.wrap(raw, width, replace_whitespace=False) or [""])
        return out

    def _banner(self, width: int) -> list[tuple[str, int]]:
        art = [
            ("", 0),
            (f"  {PRODUCT} {VERSION}", self._attr("cyan", self.c.A_BOLD)),
            ("  free models · local tools · one CLI", self._attr("cyan")),
            ("", 0),
            ("  Type a request and press Enter — the agent reads, edits, searches and runs.",
             self.c.A_DIM),
            ("  Every write shows its diff first. Try: fix the failing test   ·   /models coding",
             self.c.A_DIM),
            ("", 0),
        ]
        return [(line[: width - 1], attr) for line, attr in art]

    def _message_lines(self, width: int) -> list[tuple[str, int]]:
        key = (width, len(self.messages), self.show_tokens, self.filter)
        if self.lines_cache and self.lines_cache[0] == key:
            return self.lines_cache[1]
        lines: list[tuple[str, int]] = []
        needle = self.filter.lower()
        matches = 0
        for msg in self.messages:
            role = str(msg.get("role") or "")
            text = content_to_text(msg.get("content"))
            if needle and needle not in text.lower() and needle not in role:
                continue
            matches += 1
            if msg.get("images"):
                text += f"\n[{len(msg['images'])} image(s) attached]"
            if role == "user":
                wrapped = self._wrap(text, width - 8)
                for index, line in enumerate(wrapped):
                    prefix = "  ◆ you  " if index == 0 else "         "
                    lines.append((prefix + line, self._attr("green", self.c.A_BOLD)))
                lines.append(("", 0))
            elif role == "info":
                for line in self._wrap(text, width - 4):
                    lines.append(("   " + line, self.c.A_DIM))
            else:
                meta = msg.get("meta") or {}
                tag = ""
                if meta.get("provider"):
                    bits = [f"{meta.get('provider')}/{meta.get('model')}"]
                    if meta.get("latency_ms"):
                        bits.append(f"{float(meta['latency_ms']) / 1000:.1f}s")
                    if meta.get("tokens_out"):
                        bits.append(f"{human_count(meta.get('tokens_out', 0))} out tok")
                    tag = "  ◆ " + " · ".join(bits)
                if tag:
                    lines.append((tag, self._attr("magenta", self.c.A_DIM)))
                for line in self._wrap(text, width - 4):
                    lines.append(("   " + line, 0))
                lines.append(("", 0))
        if needle:
            lines.insert(0, (f"  filter: {self.filter} · {matches} message(s) · /find to clear",
                             self._attr("yellow")))
            lines.insert(1, ("", 0))
        self.lines_cache = (key, lines)
        return lines

    def _render_lines(self, width: int) -> list[tuple[str, int]]:
        lines: list[tuple[str, int]] = []
        if not self.messages and not self.busy and not self.filter:
            lines.extend(self._banner(width))
        lines.extend(self._message_lines(width))
        if self.busy:
            if self.stream_buf:
                key = (width, len(self.stream_buf))
                if self.stream_cache is None or self.stream_cache[0] != key:
                    self.stream_cache = (key, self._wrap(self.stream_buf, width - 4))
                for line in self.stream_cache[1]:
                    lines.append(("   " + line, 0))
                lines.append(("   ▌", self._attr("cyan")))
            else:
                spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[self.spinner % 10]
                label = "waiting for a free model" if self.spinner else "thinking"
                lines.append((f"   {spin} {label}...", self._attr("cyan", self.c.A_DIM)))
        return lines

    def _draw(self) -> None:
        self.s.erase()
        self.click_targets = []
        height, width = self.s.getmaxyx()
        if height < TUI_MIN_HEIGHT or width < TUI_MIN_WIDTH:
            self._add(0, 0, f"terminal too small ({width}x{height}) - need "
                            f"{TUI_MIN_WIDTH}x{TUI_MIN_HEIGHT}", self.c.A_BOLD)
            self.s.refresh()
            return
        # Header: brand on the left, live routing state on the right.
        brand = f" {PRODUCT} {VERSION} "
        self._add(0, 0, brand, self._attr("cyan", self.c.A_BOLD))
        self._add(0, len(brand), "· terminal coding agent", self.c.A_DIM)
        again = "● " if self.busy else ""
        right = (f"{again}{self.model} · {self.task or 'auto'} · "
                 f"{self.agent_backend or 'free pool'} ")
        if len(brand) + 24 + len(right) < width:
            self._add(0, width - len(right) - 1, right,
                      self._attr("cyan" if not self.busy else "yellow"))
        self._add(1, 0, "─" * width, self.c.A_DIM)

        top, bottom = 2, height - 5
        pane = max(1, bottom - top)
        lines = self._render_lines(width - 1)
        if self.scroll:
            end = max(0, len(lines) - self.scroll)
            start = max(0, end - pane)
            visible = lines[start:end]
        else:
            visible = lines[-pane:]
        for offset, (text, attr) in enumerate(visible):
            self._add(top + offset, 0, text[: width - 1], attr)

        self._add(height - 4, 0, "─" * width, self.c.A_DIM)
        prompt = " ❯ "
        available = width - len(prompt) - 2
        shown = self.buffer[-available:] if available > 0 else ""
        self._add(height - 3, 0, prompt, self._attr("green", self.c.A_BOLD))
        if shown:
            self._add(height - 3, len(prompt), shown)
        else:
            placeholder = "ask for a change, a fix or an explanation — /help for commands"
            self._add(height - 3, len(prompt), placeholder[: available], self.c.A_DIM)
        try:
            self.s.move(height - 3, min(width - 1, len(prompt) + display_width(shown)))
        except self.c.error:
            pass

        token_key = (len(self.messages), len(str(self.messages[-1].get("content") or ""))
                     if self.messages else 0)
        if self.ctx_cache is None or self.ctx_cache[0] != token_key:
            self.ctx_tokens = estimate_tokens("\n".join(
                str(m.get("content") or "") for m in self.messages))
            self.ctx_cache = (token_key, self.ctx_tokens)
        tokens = self.ctx_tokens
        state = "working" if self.busy else "ready"
        if self.busy and self.stream_started:
            elapsed = max(0.0, (time.monotonic() if not self.first_chunk else self.first_chunk)
                          - self.stream_started)
            state = (f"streaming {elapsed:.1f}s" if self.stream_buf
                     else f"waiting {elapsed:.1f}s")
        done = sum(1 for item in self.todos if str(item.get("status")) == "completed")
        segments = [state, f"tools {'on' if self.tools_enabled else 'off'}"]
        if self.subagents and self.tools_enabled:
            segments.append("workers on")
        if self.web_tools and self.tools_enabled:
            segments.append("web")
        if self.plan_mode:
            segments.append("plan mode")
        if self.filter:
            segments.append(f"find '{self.filter}'")
        segments.append(f"{len(self.messages)} msgs")
        segments.append(f"~{human_count(tokens)} ctx")
        if self.todos:
            segments.append(f"tasks {done}/{len(self.todos)}")
        running = sum(1 for entry in self.workers.values() if entry.get("state") == "running")
        if running:
            segments.append(f"{running} worker{'s' if running != 1 else ''} running")
        status = " " + "  │  ".join(segments)
        hint = ("Enter send · ^P model · ^S settings · ^R retry · ^F find · ^O usage · ? help · ^D quit"
                if width > 104 else "^P model · ^S settings · ^D quit")
        self._add(height - 2, 0, status[: width - 1], self.c.A_DIM)
        if len(status) + len(hint) + 2 < width:
            self._add(height - 2, width - len(hint) - 1, hint, self.c.A_DIM)
        if self.approval:
            record = self.approval
            prompt = (f" approve [{record.get('kind')}] {record.get('detail')} · "
                      f"y apply  n deny  a always")
            self._add(height - 1, 0, prompt[: width - 1], self._attr("yellow", self.c.A_BOLD))
        elif self.notice:
            self._add(height - 1, 0, self.notice[: width - 1], self._attr("yellow"))
        else:
            items: list[tuple[str, tuple[str, Any]]] = [
                (name, ("command", name)) for name in self._command_match_items()]
            if not items and self.file_matches:
                items = [(f"@{path}", ("file", path)) for path in self.file_matches]
            if items:
                col = 2
                for label, action in items:
                    if col >= width - 2:
                        break
                    shown = label[: max(0, width - col - 1)]
                    self._add(height - 1, col, shown, self.c.A_DIM)
                    self.click_targets.append((height - 1, col, col + display_width(shown) - 1, action))
                    col += display_width(shown) + 3
            else:
                self._add(height - 1, 0, f"  {self.agent_backend or self.model} · "
                                          f"enrich {'on' if self.enrich else 'off'} · "
                                          f"stream {'on' if self.stream else 'off'}"
                                          f" · /help"[: width - 1], self.c.A_DIM)
        if self.approval:
            self._draw_approval(height, width)
        elif self.overlay:
            self._draw_overlay(height, width)
        self.s.refresh()

    def _approval_lines(self, preview: str) -> list[tuple[str, int]]:
        lines: list[tuple[str, int]] = []
        for raw in (preview or "(no preview)").splitlines():
            if raw.startswith("+++") or raw.startswith("---"):
                lines.append((raw, self.c.A_DIM))
            elif raw.startswith("@@"):
                lines.append((raw, self._attr("cyan")))
            elif raw.startswith("+"):
                lines.append((raw, self._attr("green")))
            elif raw.startswith("-"):
                lines.append((raw, self._attr("red")))
            elif raw.startswith("\\"):
                lines.append((raw, self.c.A_DIM))
            else:
                lines.append((raw, 0))
        return lines or [("(no preview)", self.c.A_DIM)]

    def _draw_approval(self, height: int, width: int) -> None:
        record = self.approval or {}
        title = f" [{record.get('kind')}] {record.get('detail')} "
        lines = self._approval_lines(str(record.get("preview") or ""))
        footer = " y apply   n deny   a always   esc deny   ↑↓ scroll "
        box_h = min(max(len(lines) + 6, 10), height - 3)
        widest = max([len(title), len(footer)] + [len(text) for text, _ in lines])
        box_w = min(max(widest + 4, 46), width - 4)
        top = max(1, (height - box_h) // 2)
        left = max(1, (width - box_w) // 2)
        scroll = int(record.get("scroll") or 0)
        visible_rows = box_h - 6
        scroll = max(0, min(scroll, max(0, len(lines) - visible_rows)))
        record["scroll"] = scroll
        border = self._attr("yellow", self.c.A_BOLD)
        inner = box_w - 2
        counter = (f" {scroll + 1}-{min(len(lines), scroll + visible_rows)}/{len(lines)} "
                   if len(lines) > visible_rows else "")
        self._add(top, left, "╭" + "─" * inner + "╮", border)
        self._add(top + 1, left, "│", border)
        self._add(top + 1, left + 2, title[: max(0, inner - 2 - len(counter))], border)
        if counter:
            self._add(top + 1, left + box_w - len(counter) - 1, counter, self.c.A_DIM)
        self._add(top + 1, left + box_w - 1, "│", border)
        self._add(top + 2, left, "├" + "─" * inner + "┤", border)
        for row in range(visible_rows):
            pos = row + scroll
            text, attr = lines[pos] if pos < len(lines) else ("", 0)
            self._add(top + 3 + row, left, "│", border)
            self._add(top + 3 + row, left + 1, " " * inner)
            self._add(top + 3 + row, left + 2, text[: inner - 2], attr)
            self._add(top + 3 + row, left + box_w - 1, "│", border)
        self._add(top + box_h - 3, left, "├" + "─" * inner + "┤", border)
        self._add(top + box_h - 2, left, "│", border)
        self._add(top + box_h - 2, left + 2, footer[: inner - 2], self.c.A_DIM)
        self._add(top + box_h - 2, left + box_w - 1, "│", border)
        self._add(top + box_h - 1, left, "╰" + "─" * inner + "╯", border)

    def _command_match_items(self) -> list[str]:
        if not self.buffer.startswith("/") or " " in self.buffer:
            return []
        names = [name.split(" ")[0] for name in CHAT_COMMANDS]
        seen: list[str] = []
        for name in names:
            if name.startswith(self.buffer) and name not in seen:
                seen.append(name)
        return seen[:6]

    def _command_matches(self) -> str:
        return "  ".join(self._command_match_items())

    def _draw_overlay(self, height: int, width: int) -> None:
        overlay = self.overlay or {}
        if overlay.get("kind") == "settings":
            self._draw_settings_overlay(height, width)
            return
        items = overlay.get("items") or []
        title = str(overlay.get("title") or "")
        query = str(overlay.get("query") or "")
        if query:
            title = f"{title} [{query}]"
        footer = str(overlay.get("footer") or "↑↓ move · type to filter · enter select · esc close")
        box_h = min(len(items) + 6, height - 3)
        box_w = min(max([len(title), len(footer)]
                        + [len(str(i.get("label"))) for i in items] + [28]) + 4, width - 4)
        top = max(1, (height - box_h) // 2)
        left = max(1, (width - box_w) // 2)
        border = self._attr("cyan")
        inner = box_w - 2
        for row in range(box_h):
            self._add(top + row, left + 1, " " * inner)
        self._add(top, left, "╭" + "─" * inner + "╮", border)
        self._add(top + 1, left, "│", border)
        self._add(top + 1, left + 2, title[: inner - 2], self._attr("cyan", self.c.A_BOLD))
        self._add(top + 1, left + box_w - 1, "│", border)
        self._add(top + 2, left, "├" + "─" * inner + "┤", border)
        index = int(overlay.get("index") if overlay.get("index") is not None else 0)
        rows = max(1, box_h - 6)
        start = 0
        if len(items) > rows:
            start = max(0, min(max(0, index) - (rows - 1) // 2, len(items) - rows))
        for row in range(rows):
            pos = row + start
            self._add(top + 3 + row, left, "│", border)
            if pos < len(items):
                self.click_targets.append((top + 3 + row, left + 1, left + box_w - 2,
                                           ("overlay", pos)))
            if pos >= len(items):
                self._add(top + 3 + row, left + 1, " " * inner)
                self._add(top + 3 + row, left + box_w - 1, "│", border)
                continue
            item = items[pos]
            attr = self.c.A_REVERSE if pos == index else 0
            self._add(top + 3 + row, left + 1, " " * inner, attr)
            self._add(top + 3 + row, left + 2, str(item.get("label"))[: inner - 2], attr)
            self._add(top + 3 + row, left + box_w - 1, "│", border)
        self._add(top + box_h - 2, left, "├" + "─" * inner + "┤", border)
        self._add(top + box_h - 1, left, "│", border)
        self._add(top + box_h - 1, left + 2, footer[: inner - 2], self.c.A_DIM)
        if len(items) > rows and index >= 0:
            counter = f" {index + 1}/{len(items)} "
            self._add(top + box_h - 1, left + max(2, box_w - len(counter) - 2),
                      counter, self.c.A_DIM)
        self._add(top + box_h - 1, left + box_w - 1, "│", border)
        self._add(top + box_h, left, "╰" + "─" * inner + "╯", border)

    def _draw_settings_overlay(self, height: int, width: int) -> None:
        """Full-height settings browser: sections, search, docs and an editor."""
        overlay = self.overlay or {}
        items = overlay.get("items") or []
        query = str(overlay.get("query") or "")
        section = str(overlay.get("section") or "")
        index = int(overlay.get("index") or 0)
        mode = str(overlay.get("mode") or "list")
        if height < 14 or width < 40:
            self._add(0, 0, "enlarge the terminal to edit settings (need 40x14)",
                      self._attr("yellow", self.c.A_BOLD))
            return
        box_h = min(height - 2, 22)
        box_w = min(width - 2, 108)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        inner = box_w - 2
        border = self._attr("cyan")
        for row in range(box_h):
            self._add(top + row, left + 1, " " * inner)
        self._add(top, left, "╭" + "─" * inner + "╮", border)
        changed = sum(1 for entry in (overlay.get("base_items") or [])
                      if entry.get("changed"))
        title = f" Settings · {len(items)} shown · {changed} changed "
        self._add(top + 1, left, "│", border)
        self._add(top + 1, left + 2, title[: inner - 2], self._attr("cyan", self.c.A_BOLD))
        hint = "search: " + (query if query else "type to filter") + " "
        self._add(top + 1, left + box_w - len(hint) - 1, hint[: inner - 2], self.c.A_DIM)
        self._add(top + 1, left + box_w - 1, "│", border)
        # Section tabs. Left/Right (or Tab) moves between them.
        self._add(top + 2, left, "│", border)
        self._add(top + 2, left + 1, " " * inner)
        col = left + 2
        for name in self.settings_sections:
            label = f" {name} "
            if col + len(label) >= left + box_w - 1:
                break
            attr = (self.c.A_REVERSE | self.c.A_BOLD) if name == section else self.c.A_DIM
            self._add(top + 2, col, label, attr)
            self.click_targets.append((top + 2, col, col + len(label) - 1,
                                       ("settings_section", name)))
            col += len(label) + 1
        self._add(top + 2, left + box_w - 1, "│", border)
        self._add(top + 3, left, "├" + "─" * inner + "┤", border)
        key_w = max(16, min(27, inner // 3))
        val_w = max(8, min(14, inner // 6))
        doc_w = max(8, inner - key_w - val_w - 6)
        self._add(top + 4, left + 2,
                  f"  {'setting':<{key_w}} {'value':<{val_w}} what it does"[: inner - 2],
                  self._attr("cyan", self.c.A_DIM))
        rows = box_h - 10
        start = 0
        if len(items) > rows:
            start = max(0, min(max(0, index) - (rows - 1) // 2, len(items) - rows))
        for offset in range(rows):
            pos = start + offset
            row = top + 5 + offset
            self._add(row, left, "│", border)
            if pos >= len(items):
                self._add(row, left + 1, " " * inner)
                self._add(row, left + box_w - 1, "│", border)
                continue
            entry = items[pos]
            selected = pos == index
            attr = self.c.A_REVERSE if selected else 0
            self._add(row, left + 1, " " * inner, attr)
            marker = "▸" if selected else ("•" if entry.get("changed") else " ")
            key_text = str(entry.get("key"))[:key_w]
            val_text = setting_value_text(entry, val_w)
            doc = str(entry.get("doc") or "")
            line = f" {marker} {key_text:<{key_w}} {val_text:<{val_w}} {doc[:doc_w]}"
            self._add(row, left + 1, line[: inner], attr)
            self.click_targets.append((row, left + 1, left + box_w - 2,
                                       ("settings_row", pos)))
            self._add(row, left + box_w - 1, "│", border)
        self._add(top + 5 + rows, left, "├" + "─" * inner + "┤", border)
        detail_row = top + 6 + rows
        entry = items[index] if items and 0 <= index < len(items) else None
        if mode == "edit" and entry is not None:
            prompt = f" editing {entry.get('key')} · {str(overlay.get('draft') or '')}▏"
            self._add(detail_row, left + 2, prompt[: inner - 2],
                      self._attr("yellow", self.c.A_BOLD))
            self._add(detail_row + 1, left + 2,
                      "enter save · esc cancel · backspace delete"[: inner - 2], self.c.A_DIM)
        elif entry is not None:
            doc = str(entry.get("doc") or "") or "No description yet."
            self._add(detail_row, left + 2, doc[: inner - 2], 0)
            default = entry.get("default", _MISSING)
            kind = str(entry.get("kind") or "text")
            hint = (f"{kind} · default: {format_setting(default)}"
                    if default is not _MISSING else kind)
            if kind == "enum":
                hint += " · choices: " + ", ".join(SETTING_CHOICES.get(str(entry.get('key')), ()))
            self._add(detail_row + 1, left + 2, hint[: inner - 2], self.c.A_DIM)
        else:
            self._add(detail_row, left + 2, "no setting matches this search"[: inner - 2],
                      self.c.A_DIM)
        footer = (" ↑↓ move · ←→ section · enter edit · ctrl+r reset · esc close "
                  if mode == "list" else " enter save · esc cancel ")
        flash = str(overlay.get("flash") or "")
        if flash and mode == "list":
            footer = f" ✓ {flash} "
        self._add(top + box_h - 2, left, "│", border)
        self._add(top + box_h - 2, left + 2, footer[: inner - 2], self.c.A_DIM)
        if len(items) > rows and items:
            counter = f" {min(index + 1, len(items))}/{len(items)} "
            self._add(top + box_h - 2, left + box_w - len(counter) - 1, counter, self.c.A_DIM)
        self._add(top + box_h - 2, left + box_w - 1, "│", border)
        self._add(top + box_h - 1, left, "╰" + "─" * inner + "╯", border)


    # -- main loop --------------------------------------------------------

    def run(self) -> int:
        try:
            while True:
                self.spinner += 1
                self._pump()
                if self.notice and time.monotonic() > self.notice_until:
                    self.notice = ""
                self._draw()
                # Idle screens block on the keyboard instead of redrawing 12x a second.
                active = self.busy or bool(self.notice)
                self.s.timeout(40 if active else -1)
                try:
                    key = self.s.get_wch()
                except self.c.error:
                    continue
                except KeyboardInterrupt:
                    key = "\x03"
                if key == self.c.KEY_RESIZE:
                    continue
                if key == getattr(self.c, "KEY_MOUSE", None):
                    self._mouse()
                    continue
                if not self._key(key) or self.quitting:
                    break
        finally:
            # Always hand software flow control back, even when the TUI raises.
            self._restore_flow_control()
        try:
            self.c.mousemask(0)
        except (self.c.error, AttributeError):
            pass
        close_mcp_sessions()
        self._persist()
        return 0

    def _restore_flow_control(self) -> None:
        if self._term_attrs is None:
            return
        try:
            import termios
            fd, attrs = self._term_attrs
            termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        except (ImportError, OSError, ValueError):
            pass
        self._term_attrs = None

    def _say(self, text: str, role: str = "info") -> None:
        self.messages.append({"role": role, "content": text})
        self._persist()

    def _warn(self, text: str) -> None:
        self.notice = text
        self.notice_until = time.monotonic() + 5

    def _mouse(self) -> None:
        """Wheel scrolls the transcript; a click activates a hint or overlay row."""
        try:
            _, mx, my, _, button = self.c.getmouse()
        except (self.c.error, AttributeError):
            return
        if button & getattr(self.c, "BUTTON4_PRESSED", 0):
            self.scroll += 3
            return
        if button & getattr(self.c, "BUTTON5_PRESSED", 0):
            self.scroll = max(0, self.scroll - 3)
            return
        if button & (getattr(self.c, "BUTTON1_CLICKED", 0)
                     | getattr(self.c, "BUTTON1_PRESSED", 0)):
            for row, left, right, action in reversed(self.click_targets):
                if row == my and left <= mx <= right:
                    self._click(action)
                    return

    def _click(self, action: tuple[str, Any]) -> None:
        kind, value = action
        if kind == "command":
            self.buffer = str(value) + " "
            return
        if kind == "file":
            self.buffer = re.sub(r"(?:^|\s)@([\w./-]*)$",
                                 lambda match: match.group(0)[
                                     : match.start(1) - match.start(0)] + str(value),
                                 self.buffer)
            self.file_matches = []
            return
        if kind == "overlay":
            self._overlay_choose(int(value))
            return
        if kind == "settings_section":
            if self.overlay:
                self.overlay["section"] = str(value)
                self.overlay["query"] = ""
                self.overlay["index"] = 0
                self._settings_refilter()
            return
        if kind == "settings_row":
            self._settings_choose(int(value))

    def _key(self, key: Any) -> bool:
        c = self.c
        if self.overlay:
            return self._overlay_key(key)
        if self.approval:
            char = key.lower() if isinstance(key, str) else ""
            record = self.approval
            if key == c.KEY_UP:
                record["scroll"] = max(0, int(record.get("scroll") or 0) - 1)
                return True
            if key == c.KEY_DOWN:
                record["scroll"] = int(record.get("scroll") or 0) + 1
                return True
            if key == c.KEY_PPAGE:
                record["scroll"] = max(0, int(record.get("scroll") or 0) - 10)
                return True
            if key == c.KEY_NPAGE:
                record["scroll"] = int(record.get("scroll") or 0) + 10
                return True
            if char in {"y", "n", "a", "\x1b", "\x03"}:
                record["result"][0] = char in {"y", "a"}
                if char == "a":
                    self.auto_approve = True
                record["event"].set()
                self.approval = None
                verdict = "applied" if char in {"y", "a"} else "denied"
                self._say(f"[{record.get('kind')}] {record.get('detail')} — {verdict}")
                self._warn(verdict)
            return True
        if key in {"\x04", "\x11"}:
            return False
        if key == "\x03":
            if self.busy:
                self.cancel.set()
                self.busy = False
                self.stream_buf = ""
                self._warn("cancelled - the reply may still be in flight upstream")
            else:
                self._warn("Ctrl+D quits")
            return True
        if key in {"\x0c", "\x1b"}:
            return True
        if key == "\x08":
            self.buffer = self.buffer[:-1]
            self._refresh_file_matches()
            return True
        if key in {"\x15"}:
            self.buffer = ""
            return True
        if key == "\x17":
            self.buffer = self.buffer.rstrip()
            while self.buffer and not self.buffer[-1].isspace():
                self.buffer = self.buffer[:-1]
            return True
        if key == "\x0b":
            self._start_new_conversation()
            return True
        if key == "\x10":
            self._open_model_picker()
            return True
        if key == "\x12":
            self._retry()
            return True
        if key == "\x06":
            self.buffer = "/find "
            return True
        if key == "\x0f":
            self._open_usage()
            return True
        if key == "\x13":
            self._open_settings()
            return True
        if key == "\x08" or key == c.KEY_BACKSPACE:
            self.buffer = self.buffer[:-1]
            return True
        if key in {"\n", "\r", c.KEY_ENTER}:
            self._submit()
            return True
        if key == c.KEY_UP:
            self._history(-1)
            return True
        if key == c.KEY_DOWN:
            self._history(1)
            return True
        if key == c.KEY_PPAGE:
            self.scroll += max(3, (self.s.getmaxyx()[0] - 6) // 2)
            return True
        if key == c.KEY_NPAGE:
            self.scroll = max(0, self.scroll - max(3, (self.s.getmaxyx()[0] - 6) // 2))
            return True
        if key == c.KEY_HOME:
            self.scroll = 10 ** 6
            return True
        if key == c.KEY_END:
            self.scroll = 0
            return True
        if key == getattr(c, "KEY_F2", -1):
            self._open_settings()
            return True
        if key in {c.KEY_F1}:
            self._open_help()
            return True
        if key == "?" and not self.buffer:
            self._open_help()
            return True
        if key in {"\t", getattr(c, "KEY_TAB", "\t")}:
            self._complete_file()
            return True
        if isinstance(key, str) and key.isprintable():
            self.buffer += key
            self._refresh_file_matches()
        return True




    def _history(self, step: int) -> None:
        if not self.history:
            self._warn("no history yet")
            return
        self.history_index = max(0, min(len(self.history) - 1, self.history_index + step))
        self.buffer = self.history[self.history_index]

    # -- running a request ------------------------------------------------

    def _retry(self) -> None:
        if self.busy:
            self._warn("a request is already running - Ctrl+C cancels")
            return
        last = None
        for index in range(len(self.messages) - 1, -1, -1):
            if self.messages[index].get("role") == "user":
                last = index
                break
        if last is None:
            self._warn("nothing to retry yet")
            return
        text = content_to_text(self.messages[last].get("content"))
        del self.messages[last:]
        self._persist()
        self.buffer = text
        self._warn(f"retrying: {text[:60]}")
        self._submit()

    def _start_new_conversation(self) -> None:
        if self.busy:
            self._warn("wait for the current reply or cancel it with Ctrl+C")
            return
        self.messages = []
        self.filter = ""
        self.scroll = 0
        self.buffer = ""
        self.pending_images = []
        self.file_matches = []
        self.lines_cache = None
        self.stream_cache = None
        self.ctx_cache = None
        self._persist()
        self._warn("new conversation")

    def _submit(self) -> None:
        text = self.buffer.strip()
        self.buffer = ""
        if not text:
            return
        self.history.append(text)
        self.history_index = len(self.history)
        if text.startswith("/"):
            self._command(text)
            return
        if self.busy:
            self._warn("a request is already running - Ctrl+C cancels")
            return
        content = text
        if self.enrich and not any(m.get("role") == "user" for m in self.messages):
            content = build_prompt(content, persona=chat_system_prompt(self.persona, ""),
                                   output_format="text", max_tokens=self.max_tokens)
        if self.pending_images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": content}]
            for image in self.pending_images:
                parts.append({"type": "image_url", "image_url": {"url": image["url"]}})
            self.messages.append({"role": "user", "content": parts,
                                  "images": [image["name"] for image in self.pending_images]})
            self.pending_images = []
        else:
            self.messages.append({"role": "user", "content": content})
        self._transcript("user", content)
        self._persist()
        self.scroll = 0
        self.stream_buf = ""
        self.stream_cache = None
        self.busy = True
        self.stream_started = time.monotonic()
        self.first_chunk = 0.0
        self.cancel.clear()
        payload, model, task, skills = self._payload()
        target = self._worker
        if self.tools_enabled and not self.agent_backend:
            target = self._agent_worker
        threading.Thread(target=target, args=(payload, model, task, content, skills),
                         daemon=True).start()

    def _payload(self) -> tuple[list[dict[str, Any]], str, str, list[str]]:
        if self.tools_enabled and not self.agent_backend:
            system = agent_system_prompt(Path.cwd(), self.skill_names)
            if self.system_extra.strip():
                system += "\n\n" + self.system_extra.strip()
        else:
            system = chat_full_system(self.persona, self.system_extra, self.skill_names)
        if self.plan_mode:
            system += ("\n\nPLAN MODE: read-only. Inspect the workspace and return a concrete "
                       "plan with the files you would change. Do not edit or run commands "
                       "that modify anything.")
        payload = ([{"role": "system", "content": system}] if system else []) \
            + self.messages[-self.history_limit:]
        return payload, self.model, self.task or "", list(self.skill_names)

    def _worker(self, payload: list[dict[str, Any]], model: str, task: str,
                content: str, skills: list[str]) -> None:
        meta: dict[str, Any] = {}
        try:
            if self.agent_backend:
                answer = run_agent(self.agent_backend, content)
                self.queue.put(("done", (answer, {"provider": self.agent_backend,
                                                 "model": "headless"})))
                return
            if self.stream:
                chunks: list[str] = []
                for piece in stream_route(payload, model=model, task_hint=task or None,
                                          strategy=self.strategy, max_tokens=self.max_tokens,
                                          temperature=self.temperature, meta=meta):
                    if self.cancel.is_set():
                        break
                    chunks.append(piece)
                    self.queue.put(("chunk", piece))
                self.queue.put(("done", ("".join(chunks), meta)))
            else:
                result = route_once(payload, model=model, task_hint=task or None,
                                    strategy=self.strategy, max_tokens=self.max_tokens,
                                    temperature=self.temperature)
                self.queue.put(("done", (response_text(result),
                                         result.get("x_agent_router") or {})))
        except RuntimeError as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            self.queue.put(("error", f"{type(exc).__name__}: {exc}"))

    def _agent_worker(self, payload: list[dict[str, Any]], model: str, task: str,
                      content: str, skills: list[str]) -> None:
        payload = list(payload)  # agent_turn appends tool messages to its own copy

        def approve(kind: str, detail: str, preview: str = "") -> bool:
            if self.plan_mode and kind in {"write", "edit", "run", "mcp"}:
                self.queue.put(("notice", {"message": f"plan mode blocked {kind}: {detail}"}))
                return False
            if self.auto_approve:
                return True
            with self.approval_lock:  # one prompt at a time, workers queue up
                record: dict[str, Any] = {"kind": kind, "detail": detail,
                                          "preview": preview, "scroll": 0,
                                          "event": threading.Event(), "result": [False]}
                self.queue.put(("approve", record))
                record["event"].wait(timeout=600)
                return bool(record["result"][0])

        def on_event(kind: str, data: dict[str, Any]) -> None:
            self.queue.put(("event", (kind, data)))

        try:
            result = agent_turn(payload, model=model, task_hint=task or "coding",
                                max_rounds=self.max_rounds, approve=approve, on_event=on_event,
                                allow_outside=self.allow_outside,
                                temperature=self.temperature, max_tokens=self.max_tokens or None,
                                ctx={"subagent_rounds": self.subagent_rounds,
                                     "max_subagents": self.max_subagents},
                                allow_subagents=self.subagents)
            self.queue.put(("done", (result.get("text") or "", result.get("meta") or {})))
        except RuntimeError as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - shown in the UI
            self.queue.put(("error", f"{type(exc).__name__}: {exc}"))

    def _pump(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "chunk":
                if not self.first_chunk:
                    self.first_chunk = time.monotonic()
                self.stream_buf += str(payload)
                continue
            if kind == "approve":
                self.approval = payload
                continue
            if kind == "event":
                event_kind, data = payload
                if event_kind == "todos":
                    self.todos = [item for item in (data or []) if isinstance(item, dict)]
                elif event_kind == "subagent_start":
                    worker = int(data.get("worker") or 0)
                    files = ", ".join(data.get("files") or []) or "no files"
                    self.workers[worker] = {"task": str(data.get("task") or ""),
                                            "files": files, "state": "running",
                                            "changed": []}
                    self.messages.append({"role": "info",
                                          "content": f"++ worker {worker} started ({files})"})
                elif event_kind == "subagent_done":
                    worker = int(data.get("worker") or 0)
                    entry = self.workers.setdefault(worker, {"task": "", "files": "",
                                                            "changed": []})
                    entry["state"] = "done" if data.get("ok") else "failed"
                    entry["changed"] = [str(x) for x in (data.get("changed") or [])]
                    bit = ", ".join(entry["changed"]) or "no changes"
                    self.messages.append({"role": "info",
                                          "content": f"++ worker {worker} {entry['state']} ({bit})"})
                elif event_kind == "tool":
                    args = json.dumps(data.get("arguments") or {}, ensure_ascii=False)
                    worker = data.get("worker")
                    prefix = f"[w{worker}] " if worker else ""
                    self.messages.append({"role": "info",
                                          "content": f"{prefix}-> {data.get('name')} {args[:200]}"})
                elif event_kind == "verify":
                    command = data.get("command") or "(no checks detected)"
                    state = {True: "passed", False: "FAILED", None: "skipped"}[data.get("ok")]
                    self.messages.append({"role": "info",
                                          "content": f"verify {state}: {command}"})
                    if data.get("ok") is False:
                        self._warn("verification failed - see the transcript")
                    self.scroll = 0
                    continue
                elif event_kind == "notice":
                    self._warn(str(data.get("message") or ""))
                elif event_kind == "tool_result":
                    output = str(data.get("output") or "").rstrip()
                    lines = output.splitlines()
                    body = "\n".join("   " + line[:180] for line in lines[:18])
                    if len(lines) > 18:
                        body += "\n   ..."
                    self.messages.append({"role": "info", "content": body})
                self.scroll = 0
                continue
            if kind == "locked":
                self._warn(str(payload))
                continue
            if kind == "notice":
                message = payload.get("message") if isinstance(payload, dict) else payload
                self._warn(str(message or ""))
                continue
            self.approval = None
            if kind == "compacted":
                summary, meta = payload
                self.busy = False
                self.cancel.clear()
                self.messages = [{"role": "info", "content": "Earlier turns compacted into:"},
                                 {"role": "assistant", "content": summary, "meta": meta}]
                self._persist()
                self._warn("compacted - earlier turns replaced")
                continue
            self.busy = False
            self.stream_started = 0.0
            self.first_chunk = 0.0
            self.cancel.clear()
            if kind == "error":
                self.stream_buf = ""
                self.messages.append({"role": "info", "content": f"error: {payload}"})
                self._persist()
                continue
            text, meta = payload
            self.stream_cache = None
            if detect_refusal(str(text)):
                meta = {**(meta or {}), "refused": True}
                self._warn(REFUSAL_NOTICE)
            if not str(text).strip():
                self.messages.append({"role": "info",
                                      "content": "error: empty response from the free pool"})
                self._persist()
                continue
            self.messages.append({"role": "assistant", "content": text, "meta": meta})
            self._transcript("assistant", text, meta)
            self._persist()
            self.stream_buf = ""
            self.scroll = 0

    # -- slash commands ---------------------------------------------------

    def _command(self, line: str) -> None:
        parts = line[1:].split(" ", 1)
        command = "/" + parts[0]
        value = parts[1].strip() if len(parts) > 1 else ""
        if command in {"/exit", "/quit"}:
            self.quitting = True
            return
        if command == "/plan":
            self.plan_mode = not self.plan_mode
            self._warn("plan mode: read-only" if self.plan_mode else "plan mode off")
        elif command == "/image":
            if not value:
                if self.pending_images:
                    self._say(f"attached: {', '.join(i['name'] for i in self.pending_images)}")
                else:
                    self._warn("usage: /image <path.png|jpg|webp|gif>")
            else:
                try:
                    self.pending_images.append(load_image_attachment(value))
                    self._say(f"attached {Path(value).name} "
                              f"({len(self.pending_images)} image(s) queued)")
                except ValueError as exc:
                    self._warn(str(exc))
        elif command == "/undo-edit":
            restored = restore_last_backup()
            if restored:
                self._say(f"restored {restored} from the last backup")
            else:
                self._warn("nothing to undo")
        elif command == "/help":
            self._open_help()
        elif command in {"/model", "/config"}:
            if command == "/config":
                self._open_settings(value)
            elif value:
                self.model = value
                self._save_default_model(value)
                self._warn(f"model: {self.model}")
            else:
                self._open_model_picker()
        elif command == "/models":
            task = normalize_task(value or self.task or "chat")
            candidates = pick_models(task, limit=8, strategy=self.strategy,
                                     include_unavailable=True)
            ready = sum(1 for cand in candidates if cand.get("account"))
            rows = [f"Task: {task} · {ready} ready now"]
            for index, cand in enumerate(candidates, 1):
                why = "ready" if cand.get("account") else "; ".join(cand.get("reasons") or [])[:44]
                rows.append(f"{index}. {cand['model']['id']}  ({cand.get('score', 0):.3f}) · {why}")
            if not candidates:
                rows.append("no free model available right now")
            rows.append("Ctrl+P opens the full picker (every routable model)")
            self._say("\n".join(rows))
        elif command == "/task":
            self.task = value
            self._warn(f"task: {self.task or 'auto'}")
        elif command == "/strategy":
            if value and value not in STRATEGIES:
                self._warn(f"strategy one of: {', '.join(STRATEGIES)}")
            else:
                self.strategy = value or None
                self._warn(f"strategy: {self.strategy or 'balanced'}")
        elif command in {"/temp", "/temperature"}:
            try:
                self.temperature = max(0.0, min(2.0, float(value)))
                self._warn(f"temperature: {self.temperature}")
            except ValueError:
                self._warn("give a number 0-2")
        elif command == "/max":
            try:
                self.max_tokens = max(0, int(value))
                self._warn(f"max tokens: {self.max_tokens or 'provider default'}")
            except ValueError:
                self._warn("give a number")
        elif command == "/stream":
            self.stream = value.lower() not in {"off", "0", "false", "no"}
            self._warn(f"stream: {'on' if self.stream else 'off'}")
        elif command == "/enrich":
            self.enrich = value.lower() not in {"off", "0", "false", "no"}
            self._warn(f"enrich: {'on' if self.enrich else 'off'}")
        elif command == "/tools":
            if value:
                self.tools_enabled = value.lower() in {"on", "1", "true", "yes"}
            else:
                self.tools_enabled = not self.tools_enabled
            self._warn(f"tools: {'on' if self.tools_enabled else 'off'}")
        elif command == "/todos":
            if not self.todos:
                self._say("no task list yet - the agent adds one for multi-step work")
            else:
                rows = []
                for item in self.todos:
                    mark = {"completed": "[x]", "in_progress": "[>]"}.get(
                        str(item.get("status")), "[ ]")
                    rows.append(f"{mark} {item.get('task')}")
                self._say("\n".join(rows))
        elif command == "/workers":
            if not self.workers:
                self._say("no workers yet - the agent spawns them for independent files")
            else:
                items = []
                for number in sorted(self.workers):
                    entry = self.workers[number]
                    mark = {"running": "…", "done": "ok", "failed": "fail"}.get(
                        str(entry.get("state")), "?")
                    changed = ", ".join(entry.get("changed") or []) or entry.get("files") or "-"
                    items.append({"label": f"w{number}  {mark:<4}  {changed}"})
                self.overlay = {"kind": "text", "title": "Parallel workers",
                                "items": items, "index": 0,
                                "footer": "esc close · the transcript has each report"}
        elif command == "/agent":
            if value.lower() in {"off", "none", "router", "free"}:
                self.agent_backend = None
            elif value in AGENT_BACKENDS:
                self.agent_backend = value
            elif not value:
                pass
            else:
                self._warn(f"unknown agent: {value}")
                return
            self._warn(f"agent: {self.agent_backend or 'free pool'}")
        elif command == "/skill":
            if not value:
                self._say("skills: " + (", ".join(self.skill_names) or "(none)"))
            elif value in self.skill_names:
                self.skill_names.remove(value)
                self._warn(f"unloaded {value}")
            else:
                skill = find_skill(value)
                if skill:
                    self.skill_names.append(skill["name"])
                    self._warn(f"loaded {skill['name']}")
                else:
                    self._warn(f"unknown skill: {value}")
        elif command == "/skills":
            self._capture(lambda: cmd_skills(argparse.Namespace(
                action="list", target=None, search=value or None, json=False)))
        elif command == "/mcp":
            if value:
                self._capture(lambda: cmd_mcp(argparse.Namespace(
                    action="tools", name=value, tool=None, json=False,
                    command=None, args=None, json_args=None)))
            else:
                self._capture(lambda: cmd_mcp(argparse.Namespace(
                    action="list", name=None, tool=None, json=False,
                    command=None, args=None, json_args=None)))
        elif command == "/usage":
            days = 7
            try:
                days = int(value) if value else 7
            except ValueError:
                days = 7
            self._capture(lambda: cmd_usage(argparse.Namespace(
                days=days, by="provider", limit=8, provider=None, model=None, json=False)))
        elif command == "/settings":
            self._open_settings(value)
        elif command == "/sources":
            self._capture(lambda: cmd_sources(argparse.Namespace(json=False)))
        elif command == "/session":
            self._say(f"session: {self.session}\nmessages: {len(self.messages)}\n"
                      f"model: {self.model}")
        elif command == "/clear" or command == "/new":
            self.messages = []
            self.filter = ""
            self._persist()
            self._warn("new conversation")
        elif command == "/retry":
            self._retry()
        elif command == "/find":
            self.filter = value
            self.scroll = 0
            self._warn(f"filter: {value}" if value else "filter cleared")
        elif command == "/keys":
            self._open_help()
        elif command == "/undo":
            removed = 0
            while self.messages and removed < 2:
                self.messages.pop()
                removed += 1
            self._persist()
            self._warn(f"removed {removed} message(s)")
        elif command == "/compact":
            if self.busy:
                self._warn("wait for the current request")
            elif len(self.messages) < 4:
                self._warn("nothing to compact")
            else:
                self.busy = True
                self._warn("compacting...")
                snapshot = list(self.messages)
                target = list(self._compact_target())
                threading.Thread(target=self._compact_worker, args=(snapshot, target),
                                 daemon=True).start()
        elif command == "/export":
            target = Path(os.path.expanduser(value)) if value else (
                Path.cwd() / f"chat-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md")
            lines = [f"# {PRODUCT} chat", "", f"model: {self.model}", ""]
            for msg in self.messages:
                lines.extend([f"## {msg.get('role')}", "", str(msg.get("content") or ""), ""])
            try:
                target.write_text("\n".join(lines), encoding="utf-8")
                self._warn(f"exported to {target}")
            except OSError as exc:
                self._warn(f"export failed: {exc}")
        else:
            self._warn(f"unknown command: {command} (Ctrl+H for help)")

    def _capture(self, func: Any) -> None:
        import contextlib
        import io
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                func()
        except SystemExit as exc:
            buffer.write(str(exc))
        text = buffer.getvalue().strip()
        if text:
            self._say(text)

    def _compact_target(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def _compact_worker(self, snapshot: list[dict[str, Any]],
                        target: list[dict[str, Any]]) -> None:
        body = "\n\n".join(f"{m.get('role')}: {m.get('content')}" for m in snapshot)
        try:
            result = route_once([{"role": "user", "content":
                                  "Summarize this conversation, keeping decisions, facts, paths, "
                                  "identifiers and open questions.\n\n" + body[:120000]}],
                                model=self.model, task_hint="summarization", max_tokens=1200)
            self.queue.put(("compacted", (response_text(result),
                                          result.get("x_agent_router") or {})))
        except RuntimeError as exc:
            self.queue.put(("error", str(exc)))

    # -- overlays ---------------------------------------------------------

    def _model_picker_items(self) -> list[dict[str, Any]]:
        """Every routable model, ready ones first, cached for 30 seconds.

        Aliases and live models are shown together so the picker never hides a
        model just because its provider has no credential yet: the marker and
        the state explain what pressing Enter will do.
        """
        cached = getattr(self, "_model_items_cache", None)
        if cached and time.time() - cached[0] < 30:
            return cached[1]
        items: list[dict[str, Any]] = [
            {"label": "● auto · best free model for each task", "value": "auto",
             "available": True, "search": "auto best free model task"}]
        for alias, desc in ALIAS_DESCRIPTIONS.items():
            if alias == "auto":
                continue
            items.append({"label": f"● {alias} · {desc}", "value": alias,
                          "available": True, "search": f"{alias} {desc}".lower()})
        config = getattr(self, "config", None) or load_config()
        try:
            accounts = discover_accounts(config)
        except Exception:  # noqa: BLE001 - the catalog is still useful without accounts
            accounts = []
        accounts = [acct for acct in accounts if not acct.get("disabled")]
        accounts_by_provider: dict[str, list[dict[str, Any]]] = {}
        for acct in accounts:
            accounts_by_provider.setdefault(str(acct.get("provider")), []).append(acct)
        conn = connect()
        try:
            account_health = {acct["id"]: health_for(acct["id"], conn) for acct in accounts}
            model_health = {
                (str(row["account_id"]), str(row["model"])): dict(row)
                for row in conn.execute(
                    "SELECT account_id, model, cooldown_until FROM model_health")
            }
        finally:
            conn.close()
        catalog = load_catalog()
        rows = [m for m in catalog.get("models") or []
                if isinstance(m, dict) and m.get("routable")
                and str(m.get("free_type") or "") != "discontinued"]
        cooling = {str(m.get("provider")): provider_cooling(str(m.get("provider")))
                   for m in rows}
        rows.sort(key=lambda m: (0 if accounts_by_provider.get(str(m.get("provider")))
                                 and cooling.get(str(m.get("provider"))) == 0 else 1,
                                 str(m.get("provider")), str(m.get("id"))))
        for model in rows:
            provider = str(model.get("provider") or "")
            upstream = str(model.get("model") or "")
            provider_accounts = accounts_by_provider.get(provider) or []
            wait = cooling.get(provider, 0.0)
            if not provider_accounts:
                state, symbol = "no account added", "○"
            elif wait > 0:
                state, symbol = f"cooling {wait:.0f}s", "◌"
            elif all(is_cooling(account_health.get(acct["id"], {}))
                     or is_cooling(model_health.get((acct["id"], upstream), {}))
                     for acct in provider_accounts):
                state, symbol = "cooling", "◌"
            else:
                state, symbol = "ready", "●"
            context = model.get("context")
            ctx = f"{human_count(int(context))} ctx" if context else "ctx ?"
            kind = str(model.get("free_type") or "free")
            model_id = str(model.get("id") or "")
            items.append({
                "label": f"{symbol} {model_id} · {ctx} · {kind} · {state}",
                "value": model_id,
                "available": state == "ready",
                "search": f"{model_id} {provider} {kind} {state} {ctx}".lower(),
            })
        self._model_items_cache = (time.time(), items)
        return items

    def _overlay_refilter(self) -> None:
        if not self.overlay:
            return
        query = str(self.overlay.get("query") or "").strip().lower()
        base = self.overlay.get("base_items") or []
        if query:
            hits = [item for item in base
                    if query in str(item.get("search")
                                    or f"{item.get('label')} {item.get('value')}").lower()]
        else:
            hits = list(base)
        self.overlay["items"] = hits
        self.overlay["index"] = 0

    def _open_model_picker(self, for_setting: str | None = None) -> None:
        items = self._model_picker_items()
        ready = sum(1 for item in items if item.get("available"))
        title = f"Models · {ready} ready"
        if ready < len(items):
            title += f" · {len(items) - ready} need an account"
        self.overlay = {
            "kind": "model", "title": title,
            "items": items, "base_items": items, "index": 0, "query": "",
            "for_setting": for_setting,
            "footer": "● ready  ○ add an account  ◌ cooling · ↑↓ move · enter choose · esc",
        }

    def _open_settings(self, key: str = "") -> None:
        config = getattr(self, "config", None) or load_config()
        self.config = config
        if key:
            entries = {entry["key"]: entry for entry in setting_entries(config)}
            entry = entries.get(key)
            value = deep_get(config, key.split("."))
            if value is _MISSING:
                self._warn(f"unknown setting: {key}")
                return
            lines = [f"{key} = {format_setting(value)}"]
            if entry:
                lines.append(f"default: {format_setting(entry['default'])}")
                if entry.get("doc"):
                    lines.append(str(entry["doc"]))
                lines.append(f"type: {entry['kind']} · edit with Ctrl+S")
            self._say("\n".join(lines))
            return
        self.settings_cache = setting_entries(config)
        self.settings_sections = [name for name in SETTINGS_SECTIONS
                                  if any(entry["section"] == name
                                         for entry in self.settings_cache)]
        self.overlay = {
            "kind": "settings", "title": "Settings", "items": [],
            "base_items": self.settings_cache, "index": 0, "query": "",
            "section": self.settings_sections[0] if self.settings_sections else "",
            "mode": "list", "draft": "",
        }
        self._settings_refilter()

    # -- settings browser --------------------------------------------------

    def _settings_refilter(self, reset: bool = True) -> None:
        if not self.overlay:
            return
        overlay = self.overlay
        query = str(overlay.get("query") or "").strip().lower()
        section = str(overlay.get("section") or "")
        base = overlay.get("base_items") or []
        if query:
            hits = [entry for entry in base if query in str(entry.get("search") or "")]
        else:
            hits = [entry for entry in base if str(entry.get("section")) == section]
            if not hits:
                hits = list(base)
        overlay["items"] = hits
        if reset:
            overlay["index"] = 0
        else:
            overlay["index"] = max(0, min(int(overlay.get("index") or 0),
                                          max(0, len(hits) - 1)))

    def _settings_section(self, delta: int) -> None:
        if not self.overlay or not self.settings_sections:
            return
        current = str(self.overlay.get("section") or "")
        try:
            position = self.settings_sections.index(current)
        except ValueError:
            position = 0
        section = self.settings_sections[(position + delta) % len(self.settings_sections)]
        self.overlay["section"] = section
        self.overlay["query"] = ""
        self.overlay["index"] = 0
        self._settings_refilter()

    def _settings_selected(self) -> dict[str, Any] | None:
        if not self.overlay:
            return None
        items = self.overlay.get("items") or []
        index = int(self.overlay.get("index") or 0)
        if not items:
            return None
        return items[max(0, min(index, len(items) - 1))]

    def _save_default_model(self, value: str) -> None:
        """Keep the model picked in the TUI after it exits."""
        config = getattr(self, "config", None) or load_config()
        self.config = config
        try:
            deep_set(config, ["chat", "model"], value)
            save_config(config)
        except OSError as exc:
            self._warn(f"could not save chat.model: {exc}")

    def _settings_choose(self, position: int) -> None:
        if not self.overlay:
            return
        items = self.overlay.get("items") or []
        if not items:
            return
        position = max(0, min(position, len(items) - 1))
        self.overlay["index"] = position
        entry = items[position]
        kind = str(entry.get("kind") or "text")
        if kind == "bool":
            self._settings_apply(entry, not bool(entry.get("value")))
            return
        if kind == "model":
            self._open_model_picker(for_setting=str(entry.get("key") or "chat.model"))
            return
        if kind == "enum":
            self.overlay["mode"] = "edit"
            self.overlay["draft"] = str(entry.get("value") or "")
            return
        self.overlay["mode"] = "edit"
        value = entry.get("value")
        self.overlay["draft"] = "" if value is _MISSING else format_setting(value)

    def _settings_apply(self, entry: dict[str, Any], value: Any) -> bool:
        key = str(entry.get("key") or "")
        if not key:
            return False
        try:
            validate_setting(key, value)
        except ValueError as exc:
            self._warn(str(exc))
            return False
        config = getattr(self, "config", None) or load_config()
        self.config = config
        deep_set(config, key.split("."), value)
        try:
            save_config(config)
        except OSError as exc:
            self._warn(f"could not save {key}: {exc}")
            return False
        entry["value"] = value
        default = entry.get("default", _MISSING)
        entry["changed"] = (default is not _MISSING and value != default)
        entry["label"] = f"{key} = {setting_value_text(entry, 48)}"
        entry["search"] = " ".join((key, str(entry.get("doc") or ""),
                                     str(entry.get("section") or ""),
                                     setting_value_text(entry, 60))).lower()
        self._sync_setting(key, value)
        self.settings_cache = None
        message = f"saved {key} = {setting_value_text(entry)}"
        self._warn(message)
        if self.overlay and self.overlay.get("kind") == "settings":
            self.overlay["flash"] = message
        return True

    def _sync_setting(self, key: str, value: Any) -> None:
        """Keep the live TUI state in step with a setting changed in the overlay."""
        if key == "chat.model":
            self.model = str(value or "auto")
        elif key == "chat.stream":
            self.stream = bool(value)
        elif key == "chat.auto_enrich":
            self.enrich = bool(value)
        elif key == "chat.history_limit":
            self.history_limit = max(2, int(value or 40))
        elif key == "chat.show_token_usage":
            self.show_tokens = bool(value)
        elif key == "agent.auto_approve":
            self.auto_approve = bool(value)
        elif key == "agent.max_rounds":
            self.max_rounds = max(1, int(value or 8))
        elif key == "agent.subagents":
            self.subagents = bool(value)
        elif key == "mcp.agent":
            self.web_tools = bool(value)

    def _settings_commit(self) -> None:
        if not self.overlay:
            return
        entry = self._settings_selected()
        if entry is None:
            return
        raw = str(self.overlay.get("draft") or "")
        key = str(entry.get("key") or "")
        kind = str(entry.get("kind") or "text")
        default = entry.get("default", _MISSING)
        try:
            if kind == "json":
                parsed = json.loads(raw) if raw.strip() else None
                if not isinstance(parsed, (dict, list)):
                    raise ValueError(f"{key}: expected JSON object or array")
                value: Any = parsed
            else:
                value = coerce_setting(key, raw, "" if default is _MISSING else default)
        except (ValueError, json.JSONDecodeError) as exc:
            self._warn(str(exc))
            return
        if self._settings_apply(entry, value):
            self.overlay["mode"] = "list"
            self.overlay["draft"] = ""
            self._settings_refilter(reset=False)

    def _settings_key(self, key: Any) -> bool:
        assert self.overlay is not None
        c = self.c
        overlay = self.overlay
        mode = str(overlay.get("mode") or "list")
        if key in {"\x1b", "\x03", "\x04"}:
            if mode == "edit":
                overlay["mode"] = "list"
                overlay["draft"] = ""
            else:
                self.overlay = None
            return True
        if mode == "list" and overlay.get("flash"):
            if key not in {"\n", "\r", getattr(c, "KEY_ENTER", "\r"), " "}:
                overlay.pop("flash", None)
        if mode == "edit":
            entry = self._settings_selected()
            draft = str(overlay.get("draft") or "")
            if key in {"\n", "\r", getattr(c, "KEY_ENTER", "\r")}:
                self._settings_commit()
                return True
            if key in {"\x08", getattr(c, "KEY_BACKSPACE", "\x08")}:
                overlay["draft"] = draft[:-1]
                return True
            if key == "\x15":
                overlay["draft"] = ""
                return True
            if entry is not None and entry.get("kind") == "enum":
                choices = SETTING_CHOICES.get(str(entry.get("key")), ())
                if key in {getattr(c, "KEY_LEFT", -1), getattr(c, "KEY_RIGHT", -1)}:
                    if choices:
                        try:
                            position = choices.index(draft)
                        except ValueError:
                            position = -1 if key == getattr(c, "KEY_LEFT", -1) else 0
                        step = -1 if key == getattr(c, "KEY_LEFT", -1) else 1
                        overlay["draft"] = choices[(position + step) % len(choices)]
                    return True
            if isinstance(key, str) and key.isprintable():
                overlay["draft"] = draft + key
                return True
            return True
        items = overlay.get("items") or []
        index = int(overlay.get("index") or 0)
        if key == getattr(c, "KEY_UP", -1):
            overlay["index"] = max(0, index - 1)
            return True
        if key == getattr(c, "KEY_DOWN", -1):
            overlay["index"] = max(0, min(len(items) - 1, index + 1))
            return True
        if key == getattr(c, "KEY_PPAGE", -1):
            overlay["index"] = max(0, index - 10)
            return True
        if key == getattr(c, "KEY_NPAGE", -1):
            overlay["index"] = max(0, min(len(items) - 1, index + 10))
            return True
        if key == getattr(c, "KEY_HOME", -1):
            overlay["index"] = 0
            return True
        if key == getattr(c, "KEY_END", -1):
            overlay["index"] = max(0, len(items) - 1)
            return True
        if key == "\x12":
            entry = self._settings_selected()
            if entry is not None:
                default = entry.get("default", _MISSING)
                if default is _MISSING:
                    self._warn(f"{entry.get('key')} has no default")
                else:
                    self._settings_apply(entry, default)
            return True
        if key in {getattr(c, "KEY_LEFT", -1), getattr(c, "KEY_RIGHT", -1), "\t"}:
            delta = -1 if key == getattr(c, "KEY_LEFT", -1) else 1
            self._settings_section(delta)
            return True
        if key in {"\n", "\r", getattr(c, "KEY_ENTER", "\r"), " "}:
            if items:
                self._settings_choose(index)
            return True
        if key in {"\x08", getattr(c, "KEY_BACKSPACE", "\x08")}:
            overlay["query"] = str(overlay.get("query") or "")[:-1]
            self._settings_refilter()
            return True
        if key == "\x15":
            overlay["query"] = ""
            self._settings_refilter()
            return True
        if isinstance(key, str) and key.isprintable():
            overlay["query"] = str(overlay.get("query") or "") + key
            self._settings_refilter()
            return True
        return True

    def _open_help(self) -> None:
        items = [{"label": f"{key:<12} {desc}"} for key, desc in TUI_HELP if key or desc]
        self.overlay = {"kind": "text", "title": "Keys and commands",
                        "items": items, "index": -1}

    def _open_usage(self) -> None:
        self._open_text("Usage", lambda: cmd_usage(argparse.Namespace(
            days=7, by="provider", limit=8, provider=None, model=None, json=False)))

    def _open_text(self, title: str, func: Any) -> None:
        import contextlib
        import io
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                func()
        except SystemExit as exc:
            buffer.write(str(exc))
        lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
        self.overlay = {"kind": "text", "title": title,
                        "items": [{"label": line} for line in lines[:200]], "index": -1}

    def _overlay_key(self, key: Any) -> bool:
        assert self.overlay is not None
        kind = self.overlay.get("kind")
        if kind == "settings":
            return self._settings_key(key)
        items = self.overlay.get("items") or []
        index = int(self.overlay.get("index") or 0)
        if key in {"\x1b", "\x03", "\x04"}:
            self.overlay = None
            return True
        if kind == "model":
            if key in {self.c.KEY_UP, self.c.KEY_DOWN, self.c.KEY_PPAGE,
                       self.c.KEY_NPAGE, "\n", "\r", self.c.KEY_ENTER}:
                if key == self.c.KEY_UP:
                    self.overlay["index"] = max(0, index - 1)
                elif key == self.c.KEY_DOWN:
                    self.overlay["index"] = min(len(items) - 1, index + 1)
                elif key == self.c.KEY_PPAGE:
                    self.overlay["index"] = max(0, index - 10)
                elif key == self.c.KEY_NPAGE:
                    self.overlay["index"] = min(len(items) - 1, index + 10)
                elif items:
                    self._overlay_choose(index)
                return True
            if key in {"\x08", getattr(self.c, "KEY_BACKSPACE", "\x08")}:
                self.overlay["query"] = str(self.overlay.get("query") or "")[:-1]
                self._overlay_refilter()
                return True
            if key == "\x15":
                self.overlay["query"] = ""
                self._overlay_refilter()
                return True
            if isinstance(key, str) and key.isprintable():
                self.overlay["query"] = str(self.overlay.get("query") or "") + key
                self._overlay_refilter()
                return True
            return True
        if key in {"\n", "\r", self.c.KEY_ENTER}:
            self.overlay = None
        return True

    def _overlay_choose(self, position: int) -> None:
        if not self.overlay:
            return
        items = self.overlay.get("items") or []
        if not items:
            self.overlay = None
            return
        item = items[max(0, min(len(items) - 1, position))]
        if self.overlay.get("kind") == "model":
            value = str(item.get("value") or self.model)
            target = self.overlay.get("for_setting")
            if target:
                entry = next((entry for entry in setting_entries(self.config)
                              if entry.get("key") == target), None)
                if entry is not None and self._settings_apply(entry, value):
                    self.overlay = None
                    return
            self.model = value
            self._save_default_model(value)
            suffix = "" if item.get("available", True) else " (no account yet - it may fail)"
            self._warn(f"model: {self.model}{suffix}")
        self.overlay = None
