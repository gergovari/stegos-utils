import json
from steglib import events
import os
import socket
import socketserver
import http.server
from urllib.parse import urlparse, parse_qs


class StegRequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def address_string(self):
        if not self.client_address:
            return "unix-socket"
        if isinstance(self.client_address, str):
            return self.client_address
        return super().address_string()
        
    def log_message(self, format, *args):
        # Suppress default HTTP access logging
        pass
        
    def do_GET(self):
        self.server.app.handle_request("GET", self)

    def do_POST(self):
        if self.headers.get("Upgrade") == "stegos-stream":
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "stegos-stream")
            self.send_header("Connection", "Upgrade")
            self.end_headers()
            self.server.app.handle_stream(self)
        else:
            self.server.app.handle_request("POST", self)

class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer, http.server.HTTPServer):
    pass
    
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass

class StegServerApp:
    def __init__(self):
        self.routes = {"GET": {}, "POST": {}}
        self.stream_handler = None
        self.server = None

    def route(self, method, path):
        def decorator(f):
            self.routes[method][path] = f
            return f
        return decorator

    def on_stream(self):
        def decorator(f):
            self.stream_handler = f
            return f
        return decorator

    def handle_request(self, method, handler):
        parsed = urlparse(handler.path)
        path = parsed.path
        if path in self.routes[method]:
            try:
                body = None
                if method == "POST":
                    length = int(handler.headers.get("Content-Length", 0))
                    if length > 0:
                        body = json.loads(handler.rfile.read(length))
                
                query = parse_qs(parsed.query)
                req = {"path": path, "query": query, "body": body}
                resp = self.routes[method][path](req)
                
                if isinstance(resp, tuple) and len(resp) == 2:
                    status, data = resp
                else:
                    status, data = 200, resp
                    
                resp_bytes = json.dumps(data).encode("utf-8")
                handler.send_response(status)
                handler.send_header("Content-Type", "application/json")
                handler.send_header("Content-Length", str(len(resp_bytes)))
                handler.end_headers()
                handler.wfile.write(resp_bytes)
            except Exception as e:
                events.emit("log_exception", message="Error handling request")
                handler.send_response(500)
                handler.end_headers()
                handler.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            handler.send_response(404)
            handler.end_headers()

    def handle_stream(self, handler):
        if self.stream_handler:
            self.stream_handler(handler.rfile, handler.wfile)

    def serve_unix(self, socket_path):
        parent_dir = os.path.dirname(socket_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        if os.path.exists(socket_path):
            os.remove(socket_path)
        self.server = UnixHTTPServer(socket_path, StegRequestHandler)
        self.server.app = self
        events.emit("log_info", message=f"Listening on unix socket: {socket_path}")
        self.server.serve_forever()
        
    def serve_tcp(self, host, port):
        self.server = ThreadingHTTPServer((host, port), StegRequestHandler)
        self.server.app = self
        events.emit("log_info", message=f"Listening on tcp {host}:{port}")
        self.server.serve_forever()
