# stegos-completion.sh — Bash tab-completion for stegOS CLI tools.
#
# Provides completions for stegpkg, stegctl, and steggroup.
# Installed to /etc/bash_completion.d/ by the stegos-utils recipe.

_stegpkg() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "install reconfigure remove upgrade update list clean" -- "$cur") )
    elif [[ $cword -ge 2 && ${words[1]} == "install" ]]; then
        local pkgs=$(find /stegos/repos -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$pkgs" -- "$cur") )
    elif [[ $cword -ge 2 && ${words[1]} == "update" ]]; then
        COMPREPLY=()
    elif [[ $cword -ge 2 && (${words[1]} == "remove" || ${words[1]} == "upgrade" || ${words[1]} == "reconfigure") ]]; then
        local instances=$(find /stegos/persistent -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$instances" -- "$cur") )
    elif [[ $cword -ge 2 && ${words[1]} == "clean" ]]; then
        COMPREPLY=( $(compgen -W "-y --yes" -- "$cur") )
    fi
}
complete -F _stegpkg stegpkg

_stegctl() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "start stop status restart logs" -- "$cur") )
    elif [[ $cword -eq 2 ]]; then
        local instances=$(find /stegos/persistent -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$instances" -- "$cur") )
    elif [[ $cword -ge 3 ]]; then
        COMPREPLY=( $(compgen -W "--verbose -v --group" -- "$cur") )
    fi
}
complete -F _stegctl stegctl

_steggroup() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "init" -- "$cur") )
    elif [[ $cword -ge 2 && $prev == "init" ]]; then
        local devs=$(ls /dev/sd* /dev/vd* /dev/loop* 2>/dev/null)
        COMPREPLY=( $(compgen -W "$devs" -- "$cur") )
    elif [[ $prev == "--name" || $prev == "--domain" || $prev == "--timezone" ]]; then
        COMPREPLY=()
    else
        COMPREPLY=( $(compgen -W "--name --domain --timezone --force --non-interactive" -- "$cur") )
    fi
}
complete -F _steggroup steggroup
