_stegpkg() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "install reconfigure remove upgrade update" -- "$cur") )
    elif [[ $cword -ge 2 && ${words[1]} == "install" ]]; then
        local pkgs=$(find /stegos/repos -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$pkgs" -- "$cur") )
    elif [[ $cword -ge 2 && ${words[1]} == "update" ]]; then
        # Actually stegpkg update takes no arguments, it just runs.
        COMPREPLY=()
    elif [[ $cword -ge 2 && (${words[1]} == "remove" || ${words[1]} == "upgrade" || ${words[1]} == "reconfigure") ]]; then
        local containers=$(find /stegos/persistent -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$containers" -- "$cur") )
    fi
}
complete -F _stegpkg stegpkg

_stegctl() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "start stop status logs pull" -- "$cur") )
    elif [[ $cword -eq 2 ]]; then
        local containers=$(find /stegos/persistent -mindepth 2 -maxdepth 2 -type d -exec basename {} \; 2>/dev/null)
        COMPREPLY=( $(compgen -W "$containers" -- "$cur") )
    fi
}
complete -F _stegctl stegctl

_steggroup() {
    local cur prev words cword
    _init_completion || return
    
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "init" -- "$cur") )
    elif [[ $cword -eq 2 ]]; then
        local devs=$(ls /dev/sd* /dev/vd* /dev/loop* 2>/dev/null)
        COMPREPLY=( $(compgen -W "$devs" -- "$cur") )
    elif [[ $cword -eq 3 ]]; then
        COMPREPLY=( $(compgen -W "--name" -- "$cur") )
    fi
}
complete -F _steggroup steggroup
