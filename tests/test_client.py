import pytest
import json
import socket
from unittest.mock import Mock, patch, call
from steglib.client import StegClient

@patch("steglib.client.UnixHTTPConnection")
def test_client_stream(mock_conn):
    client = StegClient(url="unix:///run/stegos/stegos.sock")
    
    mock_conn_instance = Mock()
    mock_conn.return_value = mock_conn_instance
    
    mock_resp = Mock()
    mock_resp.status = 101
    mock_conn_instance.getresponse.return_value = mock_resp
    
    mock_sock = Mock()
    mock_conn_instance.sock = mock_sock
    
    sock = client.stream()
    assert sock == mock_sock
    
    mock_conn_instance.request.assert_called_once_with(
        "POST", "/stream", headers={"Upgrade": "stegos-stream", "Connection": "Upgrade"}
    )

@patch("steglib.client.StegClient.stream")
def test_client_call_interactive_unix(mock_stream):
    client = StegClient(url="unix:///run/stegos/stegos.sock")
    
    mock_sock = Mock()
    mock_file = Mock()
    mock_sock.makefile.return_value = mock_file
    mock_file.readline.side_effect = [
        b'{"type": "done", "result": "OK"}\n'
    ]
    mock_stream.return_value = mock_sock
    
    assert client.call_interactive("pkg.install", {"packages": ["pkg1"]}) == "OK"

@patch("steglib.client.StegClient.stream")
@patch("steglib.cli_utils.do_local_prompt")
def test_client_call_interactive_prompt(mock_prompt, mock_stream):
    client = StegClient(url="unix:///run/stegos/stegos.sock")
    
    mock_sock = Mock()
    mock_file = Mock()
    mock_sock.makefile.return_value = mock_file
    mock_file.readline.side_effect = [
        b'{"type": "prompt", "message": "msg", "choices": ["A", "B"], "default": "A", "multiple": false}\n',
        b'{"type": "done", "result": "OK"}\n',
        b''
    ]
    mock_stream.return_value = mock_sock
    
    mock_prompt.return_value = "A"
    
    client.call_interactive("pkg.install", {})
    
    mock_prompt.assert_called_once_with("msg", "text", ["A", "B"], "A", False)

@patch("steglib.client.StegClient.stream")
def test_client_call_interactive_error(mock_stream):
    client = StegClient(url="unix:///run/stegos/stegos.sock")
    
    mock_sock = Mock()
    mock_file = Mock()
    mock_sock.makefile.return_value = mock_file
    mock_file.readline.side_effect = [
        b'{"type": "error", "error": "Something went wrong"}\n'
    ]
    mock_stream.return_value = mock_sock
    
    with pytest.raises(RuntimeError, match="Something went wrong"):
        client.call_interactive("pkg.install", {})
