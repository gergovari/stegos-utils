import pytest
import sys
from unittest.mock import patch, MagicMock
from steglib.cli_utils import do_local_prompt

def test_do_local_prompt_not_tty():
    with patch("sys.stdin.isatty", return_value=False):
        assert do_local_prompt("Message", default="def") == "def"

@patch("sys.stdin.isatty", return_value=True)
@patch("questionary.checkbox")
@patch("questionary.text")
def test_do_local_prompt_multiple(mock_text, mock_checkbox, mock_tty):
    # Test fallback text (no choices)
    mock_text_inst = MagicMock()
    mock_text.return_value = mock_text_inst
    mock_text_inst.ask.return_value = "a, b, c"
    assert do_local_prompt("Msg", multiple=True) == ["a", "b", "c"]
    
    # Test fallback empty
    mock_text_inst.ask.return_value = ""
    assert do_local_prompt("Msg", multiple=True, default="def, xyz") == ["def", "xyz"]

    # Test checkbox (with choices)
    mock_chk_inst = MagicMock()
    mock_checkbox.return_value = mock_chk_inst
    mock_chk_inst.ask.return_value = ["A", "B"]
    assert do_local_prompt("Msg", choices=["A", "B"], multiple=True) == ["A", "B"]

@patch("sys.stdin.isatty", return_value=True)
@patch("questionary.select")
def test_do_local_prompt_choices(mock_select, mock_tty):
    mock_inst = MagicMock()
    mock_select.return_value = mock_inst
    
    mock_inst.ask.return_value = "A"
    assert do_local_prompt("Msg", choices=["A", "B"]) == "A"
    
    mock_inst.ask.return_value = None
    assert do_local_prompt("Msg", choices=["A", "B"], default="B") == "B"

@patch("sys.stdin.isatty", return_value=True)
@patch("questionary.text")
def test_do_local_prompt_simple(mock_text, mock_tty):
    mock_inst = MagicMock()
    mock_text.return_value = mock_inst
    
    mock_inst.ask.return_value = "hello"
    assert do_local_prompt("Msg") == "hello"
    
    mock_inst.ask.return_value = None
    assert do_local_prompt("Msg", default="world") == "world"

@patch("sys.stdin.isatty", return_value=True)
@patch("questionary.confirm")
def test_do_local_prompt_confirm(mock_confirm, mock_tty):
    mock_inst = MagicMock()
    mock_confirm.return_value = mock_inst
    
    mock_inst.ask.return_value = True
    assert do_local_prompt("Msg", prompt_type="confirm") == True
    
    mock_inst.ask.return_value = None
    assert do_local_prompt("Msg", prompt_type="confirm", default=False) == False

