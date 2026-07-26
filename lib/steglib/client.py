import json
import logging
import socket
import http.client
import urllib.request
import urllib.parse
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)

class UnixHTTPHandler(urllib.request.AbstractHTTPHandler):
    def __init__(self, socket_path):
        super().__init__()
        self.socket_path = socket_path

    def unix_open(self, req):
        return self.do_open(lambda host: UnixHTTPConnection(self.socket_path), req)

    unix_request = urllib.request.AbstractHTTPHandler.do_request_

class StegClient:
    def __init__(self, url=None):
        import os
        self.url = url or os.environ.get("STEGOS_DAEMON_URL", "unix:///run/stegos/stegos.sock")
        if self.url.startswith("unix://"):
            self.socket_path = self.url[7:]
            opener = urllib.request.build_opener(UnixHTTPHandler(self.socket_path))
            urllib.request.install_opener(opener)
        elif self.url.startswith("http://"):
            self.socket_path = None
            urllib.request.install_opener(urllib.request.build_opener())
        else:
            raise ValueError("URL must start with unix:// or http://")

    def _request(self, method, path, data=None):
        if self.url.startswith("unix://"):
            full_url = f"unix://localhost{path}"
        else:
            full_url = f"{self.url}{path}"
            
        req = urllib.request.Request(full_url, method=method)
        if data is not None:
            req.data = json.dumps(data).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as response:
                body = response.read()
                if body:
                    return json.loads(body)
                return None
        except HTTPError as e:
            body = e.read()
            try:
                err_data = json.loads(body)
                raise RuntimeError(f"API Error: {err_data.get('error', e.reason)}")
            except json.JSONDecodeError:
                raise RuntimeError(f"API Error: {e.reason} - {body.decode('utf-8')}")
        except Exception as e:
            raise RuntimeError(f"Connection Error: {e}")

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data=None):
        return self._request("POST", path, data)

    def stream(self):
        """Returns a connected socket for interactive streaming."""
        if self.socket_path:
            conn = UnixHTTPConnection(self.socket_path)
        else:
            parsed = urllib.parse.urlparse(self.url)
            conn = http.client.HTTPConnection(parsed.netloc)
            
        conn.connect()
        conn.request("POST", "/stream", headers={"Upgrade": "stegos-stream", "Connection": "Upgrade"})
        resp = conn.getresponse()
        if resp.status != 101:
            raise RuntimeError(f"Failed to upgrade connection: {resp.status} {resp.reason}")
        return conn.sock

    def call_interactive(self, action, args):
        sock = self.stream()
        f = sock.makefile("rw")
        f.write(json.dumps({"action": action, "args": args}) + "\n")
        f.flush()
        while True:
            line = f.readline()
            if not line:
                break
            msg = json.loads(line)
            if msg["type"] == "prompt":
                from steglib.cli_utils import do_local_prompt
                ans = do_local_prompt(msg["message"], msg.get("choices"), msg.get("default"), msg.get("multiple"))
                f.write(json.dumps({"answer": ans}) + "\n")
                f.flush()
            elif msg["type"] == "done":
                return msg.get("result")
            elif msg["type"] == "error":
                raise RuntimeError(msg.get("error"))
            elif msg["type"] == "log":
                import sys
                print(msg.get("message"), file=sys.stderr)
