# hyperRouter

A free-model router, a full-screen coding agent, and one CLI for OpenCode,
Freebuff and DeepSeek Harness. It discovers free models across 150 providers,
picks the best one per task, and gives the model real tools: read, write, edit,
search, run commands, keep todos, fan work out to subagents. It streams answers,
tracks usage, loads 1,700+ Agent Skills, searches and crawls the web through MCP,
and exposes an OpenAI-compatible endpoint at `http://127.0.0.1:8787/v1`.

Run `hyperrouter` with no arguments and the agent TUI opens, the way `opencode`
or `freebuff` do.

It does **not** bypass provider limits. "Free" here means pooling the free tiers you
already have (keyless endpoints, local models, signup credits, daily allowances),
tracking each quota, rotating accounts and failing over honestly. When every free
account is exhausted, the request fails with a clear error instead of quietly
spending money.

## Install

```bash
git clone https://github.com/9ssault/hyperRouter.git
cd hyperRouter && ./install.sh        # ~/.local/bin, symlinks, then init
```

`install.sh` is POSIX sh, never uses sudo, is safe to re-run, and supports
`--dry-run`, `--no-init`, `HYPERROUTER_PREFIX` and `HYPERROUTER_SRC`. Manual install
still works:

```bash
install -m 755 hyperrouter ~/.local/bin/hyperrouter && ln -sf hyperrouter ~/.local/bin/hyperRouter
```

You need Python 3.11+ (standard library only). Provider keys and local model
servers are optional — keyless providers such as Pollinations and LLM7 work out of
the box. Windows works with `pip install windows-curses` for the TUI.

```bash
hyperrouter update --check   # is the checkout behind origin/main?
hyperrouter update           # pull, then reinstall the script on PATH
hyperrouter completions bash # also zsh and fish (files in contrib/)
hyperrouter man > hyperrouter.1
```

## Quick start

```bash
hyperrouter                              # bare launch: full-screen agent TUI
hyperrouter catalog --available          # what can run right now
hyperrouter sources                      # where the catalog comes from
hyperrouter tui                          # same TUI, explicitly
hyperrouter agent "fix the failing test" # one-shot agent with tools
hyperrouter chat                         # same TUI; --plain for a REPL
hyperrouter chat "explain this traceback" --session debug
hyperrouter route "summarize this" --model auto-coding
hyperrouter delegate "1. design the schema 2. write the migration 3. review it"
hyperrouter usage --days 7 --by model
hyperrouter settings
```

## Catalogue

`hyperrouter catalog --refresh` rebuilds the catalogue from four places:

| Source | What it adds |
| --- | --- |
| [models.dev](https://models.dev) | provider base URLs, env vars, and ~500 models with $0 per-token pricing |
| OpenRouter public model list | every model priced at $0, with real context limits |
| [OmniRoute](https://github.com/cheaper-inference/OmniRoute) | free-tier type, quota and ToS risk |
| built-in registry | free tiers missing from the above (GitHub Models, Chutes, Targon, Kluster, Together, Moonshot, MiniMax, DashScope, SiliconFlow) plus local vLLM |

A refresh currently yields **~1015 models across 150 providers, 770 routable**.
`hyperrouter sources` prints the per-source counts and the last refresh report.

Add credentials for the providers you actually use:

```bash
hyperrouter providers --template --missing > ~/.config/hyperrouter/providers.env
# fill in the keys you have, then:
source ~/.config/hyperrouter/providers.env
hyperrouter service restart
hyperrouter doctor
```

Keys are read from the environment only. The router never stores provider secrets.

## Agent

The TUI is an agent, not a chatbot. The model gets ten built-in tools, every enabled
MCP server's tools, and a loop:

| Tool | What it does |
| --- | --- |
| `read_file` | numbered lines, windowed |
| `write_file` | create or overwrite (backup on overwrite) |
| `edit_file` | exact single-match replace, like a patch |
| `list_dir` | sorted entries |
| `search` | ripgrep, with a Python fallback |
| `run_command` | bash in the working directory, blocked-list guarded |
| `web_search` | keyless web search (Bing HTML), titles, links, snippets |
| `web_fetch` | fetch a URL and return clean readable text |
| `todo` | the task list shown in the status bar |
| `subagent` | fan work out to parallel workers, one file group each |
| `mcp__*` | every tool of every enabled MCP server |

Writes, edits and commands ask for approval unless you pass `--auto` or set
`agent.auto_approve`. Read-only tools never ask. Paths outside the working directory
are refused unless `agent.allow_outside` is on. When a free tier answers with
`Retry after 24s`, the loop waits and continues instead of dying.

### Diffs before writes

Every `write_file` and `edit_file` renders a unified diff of exactly what would
change, in a framed viewer inside the TUI, before anything touches disk:

```
╭──────────────────────────────────────────────────────────╮
│ [edit] /work/src/parser.py                      4-12/96   │
├──────────────────────────────────────────────────────────┤
│ --- a/parser.py                                          │
│ +++ b/parser.py                                          │
│ @@ -18,7 +18,7 @@                                       │
│ -    return tokens.split(",")                            │
│ +    return [t.strip() for t in tokens.split(",")]       │
├──────────────────────────────────────────────────────────┤
│ y apply   n deny   a always   esc deny   ↑↓ scroll       │
╰──────────────────────────────────────────────────────────╯
```

`y` applies, `n`/`esc` denies and the file is untouched, `a` applies this and every
later change, arrows and PgUp/PgDn scroll long diffs. The CLI agent prints the same
diff before its `[y/N/a]` prompt, and every decision is written to the transcript as
`[edit] path — applied/denied`.

### Quota-aware scheduling

Free tiers are the bottleneck, so concurrency is capped deliberately.

- `routing.max_concurrency` (default 3) gates concurrent upstream calls across the
  main loop and every worker, so a four-worker fan-out cannot stampede one key.
- A provider that answers 402/429/5xx goes on a cooldown taken from its
  `Retry after` header (or 90 s for quota, 45 s for upstream errors), and routing
  skips it until the cooldown expires instead of retrying it blindly.
- Workers start staggered, retry once on a rate-limit/timeout, and each LLM call
  waits for a slot rather than failing immediately.

`hyperrouter quota` and `hyperrouter usage --by provider` still report what is left.

### Parallel workers

The agent can call `subagent` with a list of `{files, task}` entries. Workers run
concurrently (up to `agent.max_subagents`, default 4), each scoped to its own files,
with their own tool loop and a short reporting prompt. `files` may not overlap: the
call is refused before a model is touched, because two workers on one file would lose
an edit. Each worker is told which files its siblings own.

Workers report status live (`++ worker 2 done (src/api.py)`), retry once by themselves
when the free pool rate-limits or times out, and return a merged answer:

```json
{
  "summary": "3/3 workers ok, changed 4 file(s): a.py, b.py, c.py, d.py",
  "workers": [{"worker": 1, "ok": true, "changed": ["a.py"], "elapsed": 12.4}],
  "changed": ["a.py", "b.py", "c.py", "d.py"],
  "shared": [],
  "failed": []
}
```

Each worker runs in its **own scratch directory** with a copy of the files it owns,
so an `rm`, a formatter or a `git checkout` in one worker cannot touch another's
work. Finished files are copied back only if the original is byte-identical to the
copy the worker started from; otherwise the file is reported under `conflicts` and
left untouched. `agent.subagent_isolation false` disables the scratch copies.

`shared` flags a file two workers both touched anyway. Workers cannot spawn workers,
approval prompts are serialised so one diff viewer is open at a time, and `/workers`
lists each worker's state and files in a framed overlay. `--no-subagents` (or
`agent.subagents false`) turns the whole thing off.

```bash
hyperrouter tui --auto                      # trust this session
hyperrouter agent "add tests for parser.py" --auto --max-rounds 12
hyperrouter agent "why is this test flaky?" --json
```

The interface itself: a header with the live model and backend, a scrolling
transcript with role markers (`◆ you`, `◆ provider/model · latency`), a rules-and-
placeholder input line, a segmented status bar (state, tools, workers, web, plan
mode, messages, context, tasks), and framed overlays for the model picker, usage,
settings and approvals. `Ctrl+L` redraws after a resize, and frames are measured in
display columns, so emoji and CJK text no longer break borders.

Around the agent:

- `/image screenshot.png` queues a png/jpg/webp/gif as a data URL on the next
  message (8 MB cap) for vision-capable free models.
- `@` starts file completion anywhere in the input; `Tab` accepts the first match.
- `/undo-edit` restores the file from the most recent edit backup.
- `/plan` is read-only mode; `/workers` shows worker state; `/tools` disables the loop.

Keys: `Enter` send, `Ctrl+P` model picker, `Ctrl+O` usage, `Ctrl+U` clear line,
`Ctrl+K` new conversation, `Ctrl+C` cancel, `Ctrl+D` quit, `F1`/`?` help,
`PgUp/PgDn` scroll. `/tools` turns the tools off for a plain chat, `/todos` shows
the agent's task list.

### Safety and verification

- **Plan mode**: `/plan` makes the session read-only. Writes, commands and non-reading
  MCP tools are refused with a transcript note, and the system prompt asks for a plan
  instead of an edit. `/plan` again returns to normal.
- **Sandboxed commands**: when `bwrap` is installed, `run_command` runs with a read-only
  root, a writable workspace, writable tool caches (`~/.cache`, `~/.npm`, `~/.cargo`,
  `~/.local/share`) and an isolated PID namespace. Set `agent.sandbox none` to opt out,
  or `agent.sandbox_network false` to cut network access inside the sandbox.
- **Per-tool approvals**: `agent.approvals.write`, `.edit`, `.run` and `.mcp_write` can
  each be turned off for unattended work; `--auto` still overrides everything.
- **Web guard**: `web_fetch` accepts only http(s), resolves the hostname, refuses
  loopback/private/link-local/reserved addresses, and re-checks every redirect hop.
  Redirect chains cannot smuggle a request into `127.0.0.1` or a metadata service.
- **Verification**: after the agent changes files, it detects the project's checks
  (`pyproject.toml`/`pytest.ini` -> `python3 -m pytest -q`, `package.json` with a test
  script -> `npm test`, `Cargo.toml`, `go.mod`, or a `Makefile` test target) and runs
  them in the sandbox. The result is printed, shown in the TUI, and returned as
  `verification` in `--json`. Pin it with
  `hyperrouter settings set agent.verify_command "make check"`, or disable the step
  with `agent.verify false`.

## Chat

`hyperrouter chat` opens the same TUI on the free pool. `--plain` gives the
line-based REPL (what you get without a TTY). Both keep sessions, skills and agent
backends.

```
/help /model /models /task /strategy /temp /max /stream /enrich
/system /persona /file /usage /settings /sources /save /load
/history /undo /new /compact /export /session /retry /clear
/skills /skill <name> /mcp [server] /agent <name|off> /init /exit
```

- Sessions persist in `~/.local/share/hyperrouter/sessions/`; `chat --continue`
  resumes the most recent one, `--session name` picks another.
- Every answer ends with the model that produced it, latency and token counts.
- Transcripts are JSONL under `~/.local/share/hyperrouter/transcripts/`.
- `chat --enrich` and `chat.auto_enrich` enrich the first prompt automatically.

## Task delegation

Requests are classified (coding, debugging, review, planning, analysis, math,
writing, summarization, translation, extraction, creative, vision, agentic,
long-context, chat) and scored per model on fit, remaining quota, health, latency,
stability and context fit.

- `hyperrouter models --task "..." --explain` shows the scoring breakdown.
- `hyperrouter pick "..."` returns just the winner.
- `routing.task_models` pins a model per task, e.g.
  `hyperrouter settings set routing.task_models.coding "chutes/Qwen/Qwen3-Coder-480B-A35B-Instruct"`.
- `hyperrouter delegate` splits a multi-step task and routes each step to the free
  model that fits it, passing earlier results forward.

## Agent backends & integrations

```bash
hyperrouter setup all --start     # clients, skills and web servers, then start the proxy
hyperrouter agents                # every harness, installed + verified flags
hyperrouter run claude            # Claude Code against the Anthropic shim
hyperrouter run codex             # Codex against the OpenAI-compatible proxy
hyperrouter run aider             # Aider with OPENAI_BASE_URL pointed at us
hyperrouter run opencode
hyperrouter run dsh
```

Supported harnesses: OpenCode, DeepSeek Harness, Claude Code, Codex, Aider, Cline,
Pi, Hermes, Grok Build, Muse Code, Antigravity, and Freebuff (in-process). The last
seven are launched with `-p`/`--message` conventions and marked *(flags unverified)*
in `hyperrouter agents` until their CLI's non-interactive syntax is confirmed. Every
harness gets the router environment (`HYPERROUTER_*`, plus `ANTHROPIC_BASE_URL` or
`OPENAI_BASE_URL`/`OPENAI_API_KEY` as appropriate) and one-shot use goes through the
same free pool.

### Claude Code without a Claude account

`hyperrouter setup claude` writes `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`
into `~/.claude/settings.json`, and the proxy serves the **Anthropic Messages API**:

- `POST /v1/messages` (streaming and non-streaming)
- `POST /v1/messages/count_tokens`
- system blocks, text blocks, base64/URL images, `tool_use` and `tool_result`
  translation in both directions, with Anthropic SSE events
  (`message_start`, `content_block_start/delta/stop`, `message_delta`, `message_stop`)
- Claude model ids are mapped onto the free pool unless they are real catalogue ids

```bash
hyperrouter setup claude
claude -p "explain this repo"      # runs on the free pool, no Anthropic key
```

Streaming is translated from a completed free-model response, so tokens arrive in
one batch rather than incrementally. Tool calls stream as a single `input_json_delta`.
This compatibility layer follows the approach of
[free-claude-code](https://github.com/alishahryar1/free-claude-code) (AGPL-3.0); no
code from that project is copied here — the translation, routing and harness code is
original and MIT.

Inside `chat`, `/agent opencode` or `/agent dsh` sends each message to that agent's
headless mode (`opencode run`, `dsh headless`) and prints the result in this CLI —
the other app's interface never opens. `/agent freebuff` answers in-process with the
same free models Freebuff's BYOK connection uses, because Freebuff ships no
non-interactive mode.

- **OpenCode**: `providers.hyperrouter` → `http://127.0.0.1:8787/v1`
- **Freebuff**: BYOK connection `hyperRouter` with `HYPERROUTER_API_KEY`
- **DSH**: patches the existing `llm-pi-ai` entry and `agent-default-model`
  (never inserts a duplicate plugin), preserving other tools' patch entries
- **Shell**: `HYPERROUTER_API_KEY` loaded from the OS keyring or a 0600 file

DSH's bundled `llm-pi-ai` already declares provider defaults, so hyperRouter edits
that entry in place and points `agent-default-model` at `hyperrouter/auto`.

## Skills (Agent Skills / SKILL.md)

```bash
hyperrouter skills defaults                      # install every default collection
hyperrouter skills list                          # 1,722 installed here
hyperrouter skills search diagram
hyperrouter skills show pdf
hyperrouter chat --skill pdf "extract the tables from invoice.pdf"
```

Fifteen collections, installed automatically by `hyperrouter setup` and by
`skills defaults` on any fresh machine:

`anthropics/skills` · `obra/superpowers` · `vercel-labs/agent-skills` ·
`addyosmani/agent-skills` · `K-Dense-AI/scientific-agent-skills` ·
`alirezarezvani/claude-skills` · `coreyhaines31/marketingskills` ·
`gamedev-skills/awesome-gamedev-agent-skills` · `bergside/awesome-design-skills` ·
`SnailSploit/Claude-Red` (79 offensive-security skills) ·
`mukul975/Anthropic-Cybersecurity-Skills` (818) · plus the single-skill packs
`humanizer`, `taste-skill`, `diagram-design`, `i-have-adhd`.

Offensive/dual-use skills are for authorised testing only — the upstream repos
state that too. Any repo with `SKILL.md` files works:
`hyperrouter skills install <owner/repo>`.

Skills are discovered in `~/.config/hyperrouter/skills`, `~/.agents/skills`,
`./.agents/skills`, `./.skills` and `./skills`. In chat, `/skill <name>` toggles one
for the session; `/skills` lists them. Only the requested skill body is injected,
size-capped, so a large library costs nothing until it is used.

Lifecycle commands:

```bash
hyperrouter skills update      # git pull every installed collection
hyperrouter skills trust       # provenance, commit, and how many scripts it ships
hyperrouter skills dedupe      # duplicate names across roots and which one wins
hyperrouter skills pin pdf     # pin a skill for this project (.hyperrouter/skills.json)
hyperrouter skills unpin pdf
```

`skills trust` is the honest one: a skill is instructions and may ship runnable
scripts. Collections with scripts are counted and flagged, each install records its
repo and commit in `.provenance.json`, and nothing runs automatically. Treat a cloned
collection the way you would treat a cloned repo.

## MCP

```bash
hyperrouter mcp defaults                # enable the web servers (setup does this)
hyperrouter mcp add-rea                 # register REA, reverse-engineer-anything
hyperrouter mcp tools ddg
hyperrouter mcp call ddg duckduckgo_web_search --json '{"query": "..."}'
hyperrouter mcp add local --command uvx --args "some-mcp-server"
```

The client speaks MCP over stdio (JSON-RPC: `initialize`, `tools/list`,
`tools/call`) and works with any stdio server. Every enabled server's tools are
injected into the agent loop as `mcp__<server>__<tool>`, so the model can search and
crawl on its own. In the TUI, servers stay alive between messages (idle sessions are
recycled after 15 minutes and closed when you quit), which is what lets a browser
navigate in one message and snapshot the same page in the next. `mcp restart` drops
the sessions, `mcp update` also refreshes the tool schemas.

MCP tools are annotated read-only or not. Read-only tools run freely; anything else
asks the same approval viewer as writes (`agent.approvals.mcp_write`).

Enabled by default, no key needed:

| Server | Tools | What it does |
| --- | --- | --- |
| `ddg` | 1 | DuckDuckGo web search |
| `playwright` | 25 | headless Chromium: navigate, snapshot, click, read pages |
| `rea` | 229 | reverse engineering |

REA's 229 tools stay out of the agent's tool list (`agent: false` in its config) so
free models are not drowned in schemas; use them with `hyperrouter mcp call rea ...`.

Registered but off until you export the named key: `brave` (`BRAVE_API_KEY`),
`tavily` (`TAVILY_API_KEY`), `exa` (`EXA_API_KEY`), `firecrawl`
(`FIRECRAWL_API_KEY`). `hyperrouter mcp defaults` turns any of them on automatically
when its key is present. The agent also has keyless `web_search` and `web_fetch`
built in, so it can look things up even with no MCP server running.

Search prefers a keyed backend (Brave, then Tavily, then Exa) and falls back to Bing
HTML. Results are cached for 15 minutes in `~/.local/share/hyperrouter/web-cache.json`,
Bing scrapes are spaced out, and the cache is pruned by age. Inspect it with:

```bash
hyperrouter web status
hyperrouter web search "python 3.14 release notes" --max-results 5
hyperrouter web fetch https://docs.python.org/3/whatsnew/3.14.html --max-chars 4000
```

Playwright needs its Chromium once:

```bash
npx -y playwright@1.64.0-alpha-1790635538000 install chromium
```

REA ([morluto/rea](https://github.com/morluto/rea)) is a 229-tool MCP server for
reverse engineering binaries, apps and runtime behaviour. `mcp add-rea` registers it
here; REA's own setup also installs its registration into OpenCode, DSH and Freebuff
and drops its skill in `~/.agents/skills`.

## Settings

`hyperrouter settings` prints every key with its default, current value and meaning;
`*` marks changed values.

```bash
hyperrouter settings set chat.stream true
hyperrouter settings set routing.auto_enrich true
hyperrouter settings set chat.model auto-coding
hyperrouter settings get chat.model
hyperrouter settings unset chat.temperature
hyperrouter settings reset --yes
hyperrouter settings edit
```

Config lives in `~/.config/hyperrouter/config.json`; data in
`~/.local/share/hyperrouter/`. `hyperrouter config` is an alias.

## Usage

```bash
hyperrouter usage                       # requests, tokens, latency, quota
hyperrouter usage --by model --days 30
hyperrouter usage --by day --json
```

Every request is recorded in SQLite with provider, model, account, status, token
counts and latency. `hyperrouter quota` shows per-account limits; `doctor` checks the
catalogue, database, service, auth, client wiring, catalogue age, active web
backends, sandbox availability, Python version and whether curses is importable.

## Development

```bash
python3 -m unittest discover -s tests -t . -v   # 40 tests, offline, stdlib only
python3 -m compileall -q hyperrouter            # syntax gate
./install.sh --dry-run                          # what the installer would do
bash -n contrib/hyperrouter.bash                # completion syntax
```

The suite covers the diff/approval path, tool sandboxing and path escape, SSRF
refusals, subagent overlap and isolation/conflict merging, verification success and
failure, skill pinning, verify-command detection and display-width handling. CI runs
the same suite on Python 3.11 and 3.13 (`.github/workflows/ci.yml`). Tests redirect
HOME and XDG to a temp directory and set `HYPERROUTER_NO_MCP=1`, so they never touch
your config or spawn a server.

`pyproject.toml` is PEP 621 metadata for editors and scanners; it deliberately
declares no console script because setuptools cannot ship the extension-less
`hyperrouter` file as a module. `install.sh` is the supported install path.

## Licence

## The proxy

```bash
hyperrouter service start
curl -s http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $(hyperrouter keys show)" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

Any OpenAI-compatible client can point at `/v1`; Claude Code can point at
`/v1/messages` instead (see above). Model aliases: `auto`,
`auto-coding`, `auto-reasoning`, `auto-long`, `auto-vision`, `auto-fast`,
`auto-quality`, `auto-cheap`, `auto-agentic`.

## Licence

MIT. The catalogue merges models.dev and OmniRoute data (both MIT).
