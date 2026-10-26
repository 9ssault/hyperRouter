# hyperRouter

A free-model router, a full-screen coding agent, and one CLI for OpenCode,
Freebuff and DeepSeek Harness. It discovers free models across 150 providers,
picks the best one per task, and gives the model real tools: read, write, edit,
search, run commands, keep todos. It streams answers, tracks usage, loads Agent
Skills, calls MCP servers, and exposes an OpenAI-compatible endpoint at
`http://127.0.0.1:8787/v1`.

It does **not** bypass provider limits. "Free" here means pooling the free tiers you
already have (keyless endpoints, local models, signup credits, daily allowances),
tracking each quota, rotating accounts and failing over honestly. When every free
account is exhausted, the request fails with a clear error instead of quietly
spending money.

## Install

```bash
git clone https://github.com/9ssault/hyperRouter.git
install -m 755 hyperRouter/hyperrouter ~/.local/bin/hyperrouter
ln -sf hyperrouter ~/.local/bin/hyperRouter
hyperrouter init
```

You need Python 3.11+ (standard library only). Provider keys and local model
servers are optional — keyless providers such as Pollinations and LLM7 work out of
the box.

## Quick start

```bash
hyperrouter catalog --available          # what can run right now
hyperrouter sources                      # where the catalog comes from
hyperrouter tui                          # full-screen agent (default for chat)
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

The TUI is an agent, not a chatbot. The model gets seven tools and a loop:

| Tool | What it does |
| --- | --- |
| `read_file` | numbered lines, windowed |
| `write_file` | create or overwrite (backup on overwrite) |
| `edit_file` | exact single-match replace, like a patch |
| `list_dir` | sorted entries |
| `search` | ripgrep, with a Python fallback |
| `run_command` | bash in the working directory, blocked-list guarded |
| `todo` | the task list shown in the status bar |

Writes, edits and commands ask `[y]es [n]o [a]lways` unless you pass `--auto` or set
`agent.auto_approve`. Read-only tools never ask. Paths outside the working directory
are refused unless `agent.allow_outside` is on. When a free tier answers with
`Retry after 24s`, the loop waits and continues instead of dying.

```bash
hyperrouter tui --auto                      # trust this session
hyperrouter agent "add tests for parser.py" --auto --max-rounds 12
hyperrouter agent "why is this test flaky?" --json
```

Keys: `Enter` send, `Ctrl+P` model picker, `Ctrl+O` usage, `Ctrl+U` clear line,
`Ctrl+K` new conversation, `Ctrl+C` cancel, `Ctrl+D` quit, `F1`/`?` help,
`PgUp/PgDn` scroll. `/tools` turns the tools off for a plain chat, `/todos` shows
the agent's task list.

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
hyperrouter setup all --start     # wire OpenCode, Freebuff and DSH
hyperrouter agents                # what each backend can do
hyperrouter run opencode          # launch a client with router env
hyperrouter run dsh
```

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
hyperrouter skills install anthropics/skills     # 20 skills, SKILL.md standard
hyperrouter skills list
hyperrouter skills show pdf
hyperrouter chat --skill pdf "extract the tables from invoice.pdf"
```

Skills are discovered in `~/.config/hyperrouter/skills`, `~/.agents/skills`,
`./.agents/skills`, `./.skills` and `./skills`. In chat, `/skill <name>` toggles one
for the session; `/skills` lists them. Only the requested skill body is injected,
size-capped, so a large library costs nothing until it is used.

## MCP

```bash
hyperrouter mcp add-rea                 # register REA, reverse-engineer-anything
hyperrouter mcp tools rea
hyperrouter mcp call rea inspect_model_artifact --json '{"path": "model.gguf"}'
hyperrouter mcp add local --command uvx --args "some-mcp-server"
hyperrouter mcp test local
```

The client speaks MCP over stdio (JSON-RPC: `initialize`, `tools/list`,
`tools/call`) and works with any stdio server. Each call starts the server, runs the
tool and exits. In chat, `/mcp` lists servers and `/mcp rea` shows its tools.

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
counts and latency. `hyperrouter quota` shows per-account limits; `doctor` checks
the catalogue, database, service, auth and client wiring.

## The proxy

```bash
hyperrouter service start
curl -s http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $(hyperrouter keys show)" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

Any OpenAI-compatible client can point at `/v1`. Model aliases: `auto`,
`auto-coding`, `auto-reasoning`, `auto-long`, `auto-vision`, `auto-fast`,
`auto-quality`, `auto-cheap`, `auto-agentic`.

## Licence

MIT. The catalogue merges models.dev and OmniRoute data (both MIT).
