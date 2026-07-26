import pytest
import sys
from unittest.mock import patch, MagicMock
from steglib.cli_utils import do_local_prompt

def test_do_local_prompt_not_tty():
    with patch("sys.stdin.isatty", return_value=False):
        assert do_local_prompt("Message", default="def") == "def"

@patch("sys.stdin.isatty", return_value=True)
@patch("builtins.input")
def test_do_local_prompt_multiple(mock_input, mock_tty):
    mock_input.return_value = "a, b, c"
    assert do_local_prompt("Msg", multiple=True) == ["a", "b", "c"]
    
    mock_input.return_value = ""
    assert do_local_prompt("Msg", multiple=True, default="def") == ["def"]

@patch("sys.stdin.isatty", return_value=True)
@patch("builtins.input")
def test_do_local_prompt_choices(mock_input, mock_tty):
    # Test valid numeric choice
    mock_input.side_effect = ["1"]
    assert do_local_prompt("Msg", choices=["A", "B"]) == "A"
    
    # Test valid string choice
    mock_input.side_effect = ["B"]
    assert do_local_prompt("Msg", choices=["A", "B"]) == "B"
    
    # Test default
    mock_input.side_effect = [""]
    assert do_local_prompt("Msg", choices=["A", "B"], default="B") == "B"
    
    # Test invalid then valid
    mock_input.side_effect = ["invalid", "2"]
    assert do_local_prompt("Msg", choices=["A", "B"]) == "B"

@patch("sys.stdin.isatty", return_value=True)
@patch("builtins.input")
def test_do_local_prompt_simple(mock_input, mock_tty):
    mock_input.return_value = "hello"
    assert do_local_prompt("Msg") == "hello"
    
    mock_input.return_value = ""
    assert do_local_prompt("Msg", default="world") == "world"

@patch("sys.stdin.isatty", return_value=True)
@patch("builtins.input")
def test_do_local_prompt_eof(mock_input, mock_tty):
    # Test that EOFError acts like an empty input (accepts default)
    mock_input.side_effect = EOFError
    assert do_local_prompt("Msg", default="world") == "world"
    
    mock_input.side_effect = EOFError
    assert do_local_prompt("Msg", choices=["A", "B"], default="B") == "B"
    
    mock_input.side_effect = EOFError
    assert do_local_prompt("Msg", multiple=True, default="def") == ["def"]

