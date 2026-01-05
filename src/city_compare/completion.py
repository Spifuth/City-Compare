"""Shell completion support for city-compare."""

from pathlib import Path

from .models import ProfileConfig
from .rent import RentDataParser


def get_city_completions(incomplete: str = "") -> list[str]:
    """
    Get city name completions for shell autocompletion.

    Args:
        incomplete: The partial city name typed so far.

    Returns:
        List of matching city names.
    """
    try:
        config = ProfileConfig.from_yaml(Path("profiles/default.yml"))
        parser = RentDataParser(config.rent_csv_path)
        all_cities = parser.list_cities()

        if not incomplete:
            return all_cities[:50]  # Return first 50 cities

        incomplete_lower = incomplete.lower()
        return [city for city in all_cities if city.lower().startswith(incomplete_lower)][:50]
    except Exception:
        return []


def generate_bash_completion() -> str:
    """Generate Bash completion script."""
    return '''# Bash completion for city-compare
# Add this to ~/.bashrc or ~/.bash_completion

_city_compare_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmd="${COMP_WORDS[1]}"

    # Commands
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "compare clear-cache serve --help --version" -- "$cur"))
        return
    fi

    # Options for compare command
    if [[ "$cmd" == "compare" ]]; then
        case "$prev" in
            -p|--profile)
                COMPREPLY=($(compgen -f -X '!*.yml' -- "$cur"))
                return
                ;;
            -r|--rules)
                COMPREPLY=($(compgen -f -X '!*.rules' -- "$cur"))
                return
                ;;
            -o|--out)
                COMPREPLY=($(compgen -f -X '!*.md' -- "$cur"))
                return
                ;;
            -j|--json)
                COMPREPLY=($(compgen -f -X '!*.json' -- "$cur"))
                return
                ;;
            --html)
                COMPREPLY=($(compgen -f -X '!*.html' -- "$cur"))
                return
                ;;
        esac

        # City completion
        if [[ "$cur" != -* ]]; then
            local cities=$(city-compare complete-city "$cur" 2>/dev/null)
            COMPREPLY=($(compgen -W "$cities" -- "$cur"))
            return
        fi

        # Options
        COMPREPLY=($(compgen -W "--profile -p --rules -r --out -o --explain -e --json -j --html --air-quality -a --no-verify-ssl --help" -- "$cur"))
    fi
}

complete -F _city_compare_completions city-compare
'''


def generate_zsh_completion() -> str:
    """Generate Zsh completion script."""
    return '''#compdef city-compare
# Zsh completion for city-compare
# Install: copy to a directory in your $fpath (e.g., ~/.zsh/completions/)

_city_compare() {
    local line state

    _arguments -C \\
        "1: :->command" \\
        "*::arg:->args"

    case "$state" in
        command)
            _values "command" \\
                "compare[Compare French cities]" \\
                "clear-cache[Clear the local cache]" \\
                "serve[Start REST API server]" \\
                "--help[Show help]" \\
                "--version[Show version]"
            ;;
        args)
            case $line[1] in
                compare)
                    _city_compare_compare
                    ;;
                serve)
                    _city_compare_serve
                    ;;
            esac
            ;;
    esac
}

_city_compare_compare() {
    _arguments \\
        "-p[Profile file]:profile:_files -g '*.yml'" \\
        "--profile[Profile file]:profile:_files -g '*.yml'" \\
        "-r[Rules file]:rules:_files -g '*.rules'" \\
        "--rules[Rules file]:rules:_files -g '*.rules'" \\
        "-o[Output file]:output:_files -g '*.md'" \\
        "--out[Output file]:output:_files -g '*.md'" \\
        "-j[JSON output]:json:_files -g '*.json'" \\
        "--json[JSON output]:json:_files -g '*.json'" \\
        "--html[HTML output]:html:_files -g '*.html'" \\
        "-e[Include explanation]" \\
        "--explain[Include explanation]" \\
        "-a[Include air quality]" \\
        "--air-quality[Include air quality]" \\
        "--no-verify-ssl[Disable SSL verification]" \\
        "*:city:_city_compare_cities"
}

_city_compare_serve() {
    _arguments \\
        "-h[Host to bind]:host:" \\
        "--host[Host to bind]:host:" \\
        "-P[Port to bind]:port:" \\
        "--port[Port to bind]:port:" \\
        "--reload[Enable auto-reload]"
}

_city_compare_cities() {
    local cities
    cities=(${(f)"$(city-compare complete-city "$words[CURRENT]" 2>/dev/null)"})
    _describe -t cities "city" cities
}

_city_compare "$@"
'''


def generate_fish_completion() -> str:
    """Generate Fish completion script."""
    return '''# Fish completion for city-compare
# Install: copy to ~/.config/fish/completions/city-compare.fish

# Disable file completion for city-compare
complete -c city-compare -f

# Commands
complete -c city-compare -n "__fish_use_subcommand" -a "compare" -d "Compare French cities"
complete -c city-compare -n "__fish_use_subcommand" -a "clear-cache" -d "Clear the local cache"
complete -c city-compare -n "__fish_use_subcommand" -a "serve" -d "Start REST API server"

# Compare options
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s p -l profile -d "Profile file" -r -F
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s r -l rules -d "Rules file" -r -F
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s o -l out -d "Output file" -r -F
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s j -l json -d "JSON output" -r -F
complete -c city-compare -n "__fish_seen_subcommand_from compare" -l html -d "HTML output" -r -F
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s e -l explain -d "Include explanation"
complete -c city-compare -n "__fish_seen_subcommand_from compare" -s a -l air-quality -d "Include air quality"
complete -c city-compare -n "__fish_seen_subcommand_from compare" -l no-verify-ssl -d "Disable SSL verification"

# City completion
complete -c city-compare -n "__fish_seen_subcommand_from compare; and not __fish_contains_opt -s p -s r -s o -s j" -a "(city-compare complete-city (commandline -ct) 2>/dev/null)"

# Serve options
complete -c city-compare -n "__fish_seen_subcommand_from serve" -s h -l host -d "Host to bind"
complete -c city-compare -n "__fish_seen_subcommand_from serve" -s P -l port -d "Port to bind"
complete -c city-compare -n "__fish_seen_subcommand_from serve" -l reload -d "Enable auto-reload"
'''


def print_completion(shell: str) -> None:
    """Print completion script for the specified shell."""
    generators = {
        "bash": generate_bash_completion,
        "zsh": generate_zsh_completion,
        "fish": generate_fish_completion,
    }

    if shell not in generators:
        raise ValueError(f"Unsupported shell: {shell}. Supported: {', '.join(generators.keys())}")

    print(generators[shell]())
