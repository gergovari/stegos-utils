import pytest
from unittest.mock import patch, call
from steglib.config import ConfigResolver

def test_init():
    resolver = ConfigResolver({"properties": {"a": {}}, "required": ["a"]}, {"b": 1}, {"c": 2}, True, False)
    assert resolver.schema == {"properties": {"a": {}}, "required": ["a"]}
    assert resolver.properties == {"a": {}}
    assert resolver.required == {"a"}
    assert resolver.pkg_conf == {"b": 1}
    assert resolver.cli_conf == {"c": 2}
    assert resolver.reconfigure is True
    assert resolver.non_interactive is False
    assert resolver.final == {}

def test_resolve_no_prompt_needed():
    # If all cli_conf provided, no prompt needed
    resolver = ConfigResolver(
        {"properties": {"a": {}}}, 
        {}, 
        {"a": "cli_val"}, 
        False, 
        False
    )
    res = resolver.resolve()
    assert res == {"a": "cli_val"}

def test_resolve_missing_required_non_interactive():
    resolver = ConfigResolver(
        {"properties": {"req": {}}, "required": ["req"]},
        {},
        {},
        False,
        True
    )
    with pytest.raises(ValueError, match="Missing required configuration values and non-interactive mode is set."):
        resolver.resolve()

def test_apply_defaults_missing_required_non_interactive():
    # If a prompt isn't strictly needed according to _needs_prompt but we somehow miss a required
    # _apply_defaults is called in non_interactive and should raise
    resolver = ConfigResolver(
        {"properties": {"req": {}}, "required": ["req"]},
        {},
        {},
        False,
        True
    )
    with pytest.raises(ValueError, match="Missing required value for 'req'"):
        resolver._apply_defaults("req", {}, True)

@patch("builtins.print")
@patch("builtins.input", side_effect=["my_val"])
def test_resolve_interactive_prompt_success(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"req": {"description": "A required val"}}, "required": ["req"]},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"req": "my_val"}
    mock_print.assert_has_calls([call("\n--- Configuration Required ---"), call("------------------------------\n")])

@patch("builtins.print")
@patch("builtins.input", side_effect=["", "valid_val"])
def test_resolve_interactive_prompt_missing_required(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"req": {}}, "required": ["req"]},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"req": "valid_val"}
    mock_print.assert_any_call("This field is required.")

@patch("builtins.print")
@patch("builtins.input", side_effect=[""])
def test_resolve_interactive_prompt_default_used_when_empty(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"opt": {"default": "def_val"}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"opt": "def_val"}

@patch("builtins.print")
@patch("builtins.input", side_effect=[""])
def test_resolve_interactive_prompt_optional_empty_input(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"opt": {}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {} # No value assigned

@patch("builtins.print")
@patch("builtins.input", side_effect=["abc", "10"])
def test_resolve_interactive_prompt_type_conversion_int(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"num": {"type": "integer"}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"num": 10}
    mock_print.assert_any_call("Invalid type. Expected integer.")

@patch("builtins.print")
@patch("builtins.input", side_effect=["abc", "10.5"])
def test_resolve_interactive_prompt_type_conversion_float(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"num": {"type": "number"}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"num": 10.5}
    mock_print.assert_any_call("Invalid type. Expected number.")

@patch("builtins.print")
@patch("builtins.input", side_effect=["yes"])
def test_resolve_interactive_prompt_type_conversion_bool(mock_input, mock_print):
    resolver = ConfigResolver(
        {"properties": {"num": {"type": "boolean"}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"num": True}

def test_resolve_uses_pkg_conf():
    resolver = ConfigResolver(
        {"properties": {"a": {}}},
        {"a": "pkg_val"},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"a": "pkg_val"}

def test_resolve_uses_defaults_non_interactive():
    resolver = ConfigResolver(
        {"properties": {"a": {"default": "def_val"}}},
        {},
        {},
        False,
        True
    )
    res = resolver.resolve()
    assert res == {"a": "def_val"}

@patch("builtins.input", side_effect=["false"])
def test_resolve_interactive_prompt_type_conversion_bool_false(mock_input):
    resolver = ConfigResolver(
        {"properties": {"num": {"type": "boolean"}}},
        {},
        {},
        False,
        False
    )
    res = resolver.resolve()
    assert res == {"num": False}

def test_apply_pkg_conf_reconfigure():
    # If reconfigure is True, pkg_conf is ignored
    resolver = ConfigResolver(
        {"properties": {"a": {}}},
        {"a": "pkg"},
        {},
        True,
        False
    )
    assert resolver._apply_pkg_conf("a") is False

def test_apply_pkg_conf_no_reconfigure():
    # If reconfigure is False, pkg_conf is used
    resolver = ConfigResolver(
        {"properties": {"a": {}}},
        {"a": "pkg"},
        {},
        False,
        False
    )
    assert resolver._apply_pkg_conf("a") is True
    assert resolver.final == {"a": "pkg"}

def test_apply_defaults_non_interactive():
    # If non_interactive, default is used
    resolver = ConfigResolver(
        {"properties": {"a": {"default": "def"}}},
        {},
        {},
        False,
        True
    )
    assert resolver._apply_defaults("a", {"default": "def"}, False) is True
    assert resolver.final == {"a": "def"}

def test_apply_defaults_interactive():
    # If interactive, default is NOT used here (it's handled in prompt_user)
    resolver = ConfigResolver(
        {"properties": {"a": {"default": "def"}}},
        {},
        {},
        False,
        False
    )
    assert resolver._apply_defaults("a", {"default": "def"}, False) is False
    assert resolver.final == {}
