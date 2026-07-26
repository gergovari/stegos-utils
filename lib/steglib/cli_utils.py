import sys

def do_local_prompt(message, choices=None, default=None, multiple=False):
    if not sys.stdin.isatty():
        return default

    def _get_input(prompt_text):
        try:
            return input(prompt_text).strip()
        except EOFError:
            print()
            return ""

    if multiple:
        default_str = default if default else ""
        print(f"\n{message}")
        ans = _get_input(f"Select choices (comma-separated, or empty to skip) [default: {default_str}]: ")
        if not ans and default_str:
            ans = default_str
        if ans:
            return [x.strip() for x in ans.split(",") if x.strip()]
        return []
    
    if choices:
        print(f"\n{message}")
        for i, choice in enumerate(choices, 1):
            print(f"  {i}. {choice}")
        default_str = f" [default: {default}]" if default else ""
        while True:
            ans = _get_input(f"Select [1-{len(choices)}]{default_str}: ")
            if not ans and default:
                return default
            if ans.isdigit() and 1 <= int(ans) <= len(choices):
                return choices[int(ans) - 1]
            if ans in choices:
                return ans
            if not ans and not default:
                print("Invalid selection. Try again.")
            else:
                print("Invalid selection. Try again.")
    else:
        default_str = f" [default: {default}]" if default else ""
        ans = _get_input(f"{message}{default_str}: ")
        return ans if ans else default
