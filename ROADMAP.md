# HyperRouter overhaul roadmap

This roadmap reflects the requested staged direction: keep the terminal interface as the primary, polished experience first, then add an optional web interface. Chat, sessions, tool approvals, model/routing controls, project context, settings/accounts, workers, and plans belong to the same product surface. The web UI should share the router's existing session, event, tool, and approval APIs rather than create a second implementation of agent behavior.

## Current foundation

The current checkout already has substantial pieces to build on:

- A dependency-free Python CLI/TUI, provider catalog and routing, an OpenAI-compatible HTTP API, persisted usage, quota-aware cooldowns, and environment-referenced credentials.
- An in-process coding agent with streamed JSON events, tool approval/diff previews, MCP, project skills, todos, verification, and isolated subagents.
- Persistent named conversations and transcripts, searchable/editable settings, a model picker, `/workers`, plan mode, image attachments, and `@file` completion.
- A small-module extraction path in `hyperrouter_lib/`, now including the TUI and project quick-open helper.

The goal is not to replace those working paths. It is to close their interaction and lifecycle gaps, establish stable shared interfaces, and then put a second interface over them.

## Stage 1 — finish the terminal workspace

Deliver a cohesive, screen-first agent workspace while preserving the current keyboard-first and plain-chat fallbacks.

1. **Workspace frame and navigation:** organize the existing transcript, project context, model/routing state, tools, tasks/workers, and approvals into discoverable views. Keep the present fast path for typing and sending; add clear navigation and command discovery instead of hiding slash commands.
2. **Sessions:** searchable session/transcript browser, resume into the selected conversation, and safe new/rename/archive/delete operations. Show which records are resumable versus read-only transcripts. Preserve existing JSON session compatibility.
3. **Tools and approvals:** dedicated activity/history view showing tool arguments/results, pending approval counts, clear diffs/command previews, and explicit approve/deny. Keep mutating actions approval-gated by default; `--auto` remains an explicit opt-in.
4. **Models and routing:** make task type, strategy, selected model, provider/account readiness, quota, cooldown, and routing rationale legible together. Preserve aliases and the existing model-ranking implementation.
5. **Project context:** expose current working directory, indexed files, loaded skills, and context size; make file/skill selection inspectable and removable. Keep indexing bounded and opt-in where it may be expensive.
6. **Settings and accounts:** retain the existing validated settings editor; provide an account/provider view that never reveals secret values and offers deliberate setup/test/disable actions.
7. **Workers and plans:** show worker progress, owned files, outcomes/conflicts, todos and plan state in a first-class view, while keeping `/workers`, `/todos`, and `/plan` working.
8. **Reliability and accessibility:** test resize, narrow terminals, Unicode, cancellation, long output, reconnect/resume and terminal-state restoration. Continue supporting plain chat on terminals without curses.

**Stage 1 acceptance:** users can switch sessions, identify active routing and project context, inspect tool activity, decide approvals, configure non-secret settings, and track workers/plans without leaving the TUI; existing CLI commands and data remain compatible.

## Stage 2 — extract shared agent/session services

Before building a second UI, move behavior that must be identical behind provider-neutral application services: session repository, event stream, agent run lifecycle, cancellation, tool invocation, approval decisions, model/routing queries, settings/accounts, todos and workers. Keep the CLI commands and TUI as adapters. Define versioned request/event shapes and explicit ownership for concurrent runs; avoid starting a second agent loop or duplicating tool safety rules in a frontend.

**Stage 2 acceptance:** CLI/TUI and headless clients consume the same session/agent APIs; event ordering, cancellation, approval defaults, and persistence are covered by deterministic tests.

## Stage 3 — optional web workspace

Add a separately enabled local web UI only after the shared service boundary is stable. Reuse the same workspace concepts and APIs: chat/session navigation, tools and approvals, model/routing, project context, settings/accounts, workers/plans. Bind to loopback by default, require an explicit authenticated key/session for browser access, and use the existing HTTP router authentication rather than exposing provider credentials to browser JavaScript. The frontend is optional; the CLI remains complete and usable without it.

**Stage 3 acceptance:** web and TUI can observe and control the same persisted sessions and run events; browser origin/auth protections and approval flows are tested; disabling the web surface leaves no required service or dependency behind.

## Cross-cutting work, in order

- Continue extracting cohesive modules from the large executable script without introducing mandatory runtime dependencies.
- Review filesystem/process/network/provider boundaries and error handling as each service is extracted; do not bundle unrelated safety changes into UI work.
- Add focused tests at module/service boundaries, then full Python-version CI and install/upgrade checks.
- Measure installed-launcher startup and representative TUI response before claiming performance changes.
- Update CLI help and docs alongside each delivered stage. Keep release notes and protocol/API changes explicit.

## First safe tranche in this checkout

The first tranche is deliberately narrow: finish TUI ownership boundaries by extracting the curses application and its `@file` completion/reset helpers, make the new-conversation shortcut consistently clear visible state while protecting in-flight work, and preserve cooldown behavior across provider failures/restarts with offline tests. This reduces the executable's UI surface and improves the existing user's workflow without starting a new frontend, adding dependencies, changing agent semantics, or expanding network exposure. The next tranche should add a tested session browser and then define shared event/session service contracts before any web implementation.
