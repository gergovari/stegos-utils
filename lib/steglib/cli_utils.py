import sys
import questionary
from questionary import Validator, ValidationError

class EmailValidator(Validator):
    def validate(self, document):
        val = document.text
        if not ("@" in val and "." in val.split("@")[1]):
            raise ValidationError(message="Please enter a valid email address", cursor_position=len(val))

class DomainValidator(Validator):
    def validate(self, document):
        val = document.text
        if not ("." in val and " " not in val):
            raise ValidationError(message="Please enter a valid domain name", cursor_position=len(val))

class IntegerValidator(Validator):
    def validate(self, document):
        val = document.text
        if not val.lstrip('-').isdigit():
            raise ValidationError(message="Please enter a valid integer", cursor_position=len(val))

class NumberValidator(Validator):
    def validate(self, document):
        val = document.text
        try:
            float(val)
        except ValueError:
            raise ValidationError(message="Please enter a valid number", cursor_position=len(val))

def do_local_prompt(message, prompt_type="text", choices=None, default=None, multiple=False):
    if not sys.stdin.isatty():
        return default

    if prompt_type == "multiselect" or multiple:
        default_choices = []
        if default:
            default_choices = [x.strip() for x in str(default).split(",")]
        
        if not choices:
            # Fallback if no choices provided but multiple is requested
            ans = questionary.text(f"{message} (comma-separated)", default=str(default) if default else "").ask()
            if ans is None:
                return []
            if ans.strip():
                return [x.strip() for x in ans.split(",")]
            return default_choices
            
        ans = questionary.checkbox(message, choices=choices).ask()
        return ans if ans is not None else []

    if prompt_type == "select" or (choices and not multiple):
        def_str = str(default) if default is not None else None
        ans = questionary.select(message, choices=choices, default=def_str).ask()
        return ans if ans is not None else default

    if prompt_type == "confirm":
        def_bool = True
        if default is not None:
            if isinstance(default, bool):
                def_bool = default
            else:
                def_bool = str(default).lower() in ("y", "yes", "true", "1")
        ans = questionary.confirm(message, default=def_bool).ask()
        return ans if ans is not None else default

    if prompt_type == "password":
        ans = questionary.password(message).ask()
        return ans if ans else default

    # Basic text based prompts
    val_map = {
        "email": EmailValidator,
        "domain": DomainValidator,
        "integer": IntegerValidator,
        "number": NumberValidator
    }
    
    validator = val_map.get(prompt_type)
    ans = questionary.text(message, default=str(default) if default is not None else "", validate=validator).ask()
    
    if ans is None:
        return default
        
    if not ans:
        return default if default is not None else ""
        
    if prompt_type == "integer":
        return int(ans)
    elif prompt_type == "number":
        return float(ans)
        
    return ans

import argparse
import logging
from steglib.client import StegClient

def setup_cli(description, version_str):
    try:
        from rich_argparse import RichHelpFormatter
        formatter_class = RichHelpFormatter
    except ImportError:
        formatter_class = argparse.HelpFormatter

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parent_parser.add_argument("--daemon-url", help="URL of the stegd daemon (default: unix:///run/stegos/stegos.sock or STEGOS_DAEMON_URL)")

    parser = argparse.ArgumentParser(description=description, formatter_class=formatter_class, parents=[parent_parser])
    parser.add_argument('--version', action='version', version=version_str)
    
    return parser, parent_parser, formatter_class

def init_cli_client(args):
    # Hack to fix argparse subparser overwriting the global verbose flag
    if "-v" in sys.argv or "--verbose" in sys.argv:
        args.verbose = True
        
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")
    client = StegClient(url=args.daemon_url)
    return client
