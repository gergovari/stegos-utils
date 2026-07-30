import pytest
from unittest.mock import Mock, patch
from steglib.server import StegServerApp, StegRequestHandler
from socketserver import BaseRequestHandler
import socket
import json
import threading

def test_steg_server_app_decorator():
    app = StegServerApp()
    
    @app.on_stream()
    def handler(rfile, wfile):
        pass
        
    assert app.stream_handler == handler

@patch("steglib.server.UnixHTTPServer")
@patch("steglib.server.os.chmod", create=True)
@patch("steglib.server.os.remove")
@patch("steglib.server.os.path.exists", return_value=True)
def test_steg_server_app_serve_unix(mock_exists, mock_remove, mock_chmod, mock_server):
    app = StegServerApp()
    
    mock_server_instance = Mock()
    mock_server.return_value = mock_server_instance
    
    app.serve_unix("/tmp/test.sock")
    
    mock_server.assert_called_once()
    mock_remove.assert_called_once_with("/tmp/test.sock")
    mock_server_instance.serve_forever.assert_called_once()

@patch("steglib.server.ThreadingHTTPServer")
def test_steg_server_app_serve_tcp(mock_server):
    app = StegServerApp()
    
    mock_server_instance = Mock()
    mock_server.return_value = mock_server_instance
    
    app.serve_tcp("127.0.0.1", 8080)
    
    mock_server.assert_called_once()
    mock_server_instance.serve_forever.assert_called_once()
