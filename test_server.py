import socketserver
import http.server
import os

class UnixHTTPServer(socketserver.UnixStreamServer, http.server.HTTPServer):
    pass

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"hello")

if os.path.exists("test.sock"): os.remove("test.sock")
server = UnixHTTPServer("test.sock", Handler)
print("Server created")
