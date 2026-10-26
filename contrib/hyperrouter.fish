# fish completion for hyperRouter
# install: cp contrib/hyperrouter.fish ~/.config/fish/completions/hyperrouter.fish

# Commands
complete -c hyperrouter -f -n '__fish_use_subcommand' -a init -d 'create config, database, protocol, and catalog'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a catalog -d 'list or refresh the free-model catalog'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a sources -d 'show which free sources the catalog came from'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a providers -d 'list providers and configured account counts'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a models -d 'rank free models for a task'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a pick -d 'pick the single best free model for a task'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a prompt -d 'build an enriched prompt'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a enrich -d 'alias for prompt'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a route -d 'run one request through the best free model'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a web -d 'check, search and fetch from the web'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a update -d 'pull a newer hyperRouter and reinstall the script'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a completions -d 'print shell completion for bash, zsh or fish'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a man -d 'print a roff man page for this CLI'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a skills -d 'list, inspect and install Agent Skills'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a mcp -d 'manage and call MCP servers'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a chat -d 'interactive chat on the free pool'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a delegate -d 'split a task and route each step'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a agents -d 'list agent backends usable inside hyperRouter'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a tui -d 'full-screen chat and agent TUI'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a agent -d 'coding agent: read, edit, search and run commands'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a serve -d 'run the OpenAI-compatible proxy'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a service -d 'start, stop or check the proxy'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a accounts -d 'manage provider account references'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a quota -d 'show per-account usage and remaining quota'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a usage -d 'show requests, tokens, latency and quota'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a stats -d 'alias for usage'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a keys -d 'generate and manage the local router API key'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a setup -d 'wire the router into OpenCode, Freebuff and DSH'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a run -d 'launch an agent with router environment variables'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a doctor -d 'check catalog, accounts, service and integrations'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a settings -d 'show or change hyperRouter settings'
complete -c hyperrouter -f -n '__fish_use_subcommand' -a config -d 'alias for settings'

# Global flags
complete -c hyperrouter -l help -d 'show help and exit'
complete -c hyperrouter -l version -d 'show the version and exit'

# Sub-actions
complete -c hyperrouter -f -n '__fish_seen_subcommand_from skills' -a 'list show install install-defaults defaults sync update trust dedupe pin unpin remove path'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from mcp' -a 'list add add-rea defaults restart update remove enable disable test tools call'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from web' -a 'status search fetch'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from service' -a 'start stop status restart'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from keys' -a 'status list generate rotate show env revoke'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from accounts' -a 'list add remove enable disable test'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from settings config' -a 'show get set unset reset edit path keys'
complete -c hyperrouter -f -n '__fish_seen_subcommand_from completions' -a 'bash zsh fish'

# Path arguments
complete -c hyperrouter -n '__fish_seen_subcommand_from agent' -F
complete -c hyperrouter -n '__fish_seen_subcommand_from run' -a 'opencode freebuff dsh'
complete -c hyperrouter -n '__fish_seen_subcommand_from skills; and __fish_seen_subcommand_from show install remove pin' -F
complete -c hyperrouter -n '__fish_seen_subcommand_from prompt route delegate' -F
