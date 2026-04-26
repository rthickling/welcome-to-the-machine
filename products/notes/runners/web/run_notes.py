#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = 8765


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        if self.path.endswith(".wasm"):
            self.send_header("Content-Type", "application/wasm")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    url = f"http://{HOST}:{PORT}/runners/web/notes-web-runner.html"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving Notes WebAssembly runner at {url}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
