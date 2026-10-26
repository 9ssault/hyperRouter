# bash completion for hyperrouter / hyperRouter
# install: cp contrib/hyperrouter.bash /etc/bash_completion.d/hyperrouter
#      or: source contrib/hyperrouter.bash

_hyperrouter_commands="init catalog sources providers models pick prompt enrich route web update completions man skills mcp chat delegate agents tui agent serve service accounts quota usage stats keys setup run doctor settings config"

_hyperrouter_skills_actions="list show install install-defaults defaults sync update trust dedupe pin unpin remove path"

_hyperrouter_web_actions="status search fetch"

_hyperrouter_mcp_actions="list add add-rea defaults restart update remove enable disable test tools call"

_hyperrouter_settings_actions="show get set unset reset edit path keys"

_hyperrouter_service_actions="start stop status restart"

_hyperrouter_keys_actions="status list generate rotate show env revoke"

_hyperrouter_accounts_actions="list add remove enable disable test"

_hyperrouter_mcp_presets="rea ddg playwright brave tavily exa firecrawl"

_hyperrouter_completions_shells="bash zsh fish"

_hyperrouter_run_targets="opencode freebuff dsh"

_hyperrouter_files() {
  if declare -F _filedir >/dev/null 2>&1; then
    _filedir
  else
    COMPREPLY=($(compgen -f -- "$1" 2>/dev/null))
  fi
}

_hyperrouter() {
  local cur prev command action
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  command="${COMP_WORDS[1]}"
  action="${COMP_WORDS[2]}"

  if [ "$COMP_CWORD" -eq 1 ]; then
    COMPREPLY=($(compgen -W "$_hyperrouter_commands" -- "$cur"))
    return 0
  fi

  case "$command" in
    agent)
      _hyperrouter_files "$cur"
      ;;
    run)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_run_targets" -- "$cur"))
      else
        _hyperrouter_files "$cur"
      fi
      ;;
    skills)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_skills_actions" -- "$cur"))
      elif [ "$action" = "show" ] || [ "$action" = "remove" ] || [ "$action" = "pin" ]; then
        _hyperrouter_files "$cur"
      elif [ "$action" = "install" ]; then
        _hyperrouter_files "$cur"
      fi
      ;;
    completions)
      COMPREPLY=($(compgen -W "$_hyperrouter_completions_shells" -- "$cur"))
      ;;
    web)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_web_actions" -- "$cur"))
      elif [ "$action" = "fetch" ]; then
        COMPREPLY=($(compgen -W "https:// http://" -- "$cur"))
      fi
      ;;
    mcp)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_mcp_actions" -- "$cur"))
      elif [ "$COMP_CWORD" -eq 3 ] && [ "$action" = "add" ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_mcp_presets" -- "$cur"))
      fi
      ;;
    settings|config)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_settings_actions" -- "$cur"))
      fi
      ;;
    service)
      COMPREPLY=($(compgen -W "$_hyperrouter_service_actions" -- "$cur"))
      ;;
    keys)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_keys_actions" -- "$cur"))
      fi
      ;;
    accounts)
      if [ "$COMP_CWORD" -eq 2 ]; then
        COMPREPLY=($(compgen -W "$_hyperrouter_accounts_actions" -- "$cur"))
      fi
      ;;
    prompt|enrich|route|delegate)
      _hyperrouter_files "$cur"
      ;;
  esac
  return 0
}

complete -F _hyperrouter hyperrouter
complete -F _hyperrouter hyperRouter
complete -F _hyperrouter agent-router
