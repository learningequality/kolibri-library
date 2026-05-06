#!/usr/bin/env python
"""
Tiny local server for hands-on testing of PraDigi HTML5 apps on a real
Android device. Lists every html5 node from the Kolibri-imported DB,
serves the (Android-fixed) zip contents for each, and prints the LAN URL
to open on your tablet.

    ./scripts/html5_test_server.py            # port 8080
    ./scripts/html5_test_server.py --port 9000

Open the printed URL on the tablet; tap an app title to launch it.
"""
import argparse
import http.server
import os
import socket
import socketserver
import sqlite3
import tempfile
import threading
import urllib.parse
import zipfile

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fresh_chef import KOLIBRI_DB, storage_path, prepare_html5_zip


EXTRACT_ROOT = tempfile.mkdtemp(prefix="pradigi-html5-test-")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def list_html5_apps():
    """Return [(node_id, title, zip_checksum, language)] sorted by title."""
    conn = sqlite3.connect(KOLIBRI_DB)
    rows = conn.execute(
        """
        SELECT n.id, n.title, f.local_file_id, n.lang_id
        FROM content_contentnode n
        JOIN content_file f ON f.contentnode_id=n.id
        WHERE n.kind='html5' AND f.extension='zip' AND n.available=1
        GROUP BY n.id
        ORDER BY n.title
        """
    ).fetchall()
    return rows


def ensure_extracted(checksum):
    """Extract the fixed zip to EXTRACT_ROOT/{checksum}/ on first request."""
    dest = os.path.join(EXTRACT_ROOT, checksum)
    if os.path.isdir(dest):
        return dest
    src = prepare_html5_zip(checksum)
    with zipfile.ZipFile(src) as zf:
        zf.extractall(dest)
    return dest


class Handler(http.server.SimpleHTTPRequestHandler):
    apps = []

    def do_GET(self):
        path = urllib.parse.unquote(self.path)
        if path == "/" or path == "/index":
            self.send_listing()
            return
        if path.startswith("/app/"):
            parts = path.lstrip("/").split("/", 2)
            if len(parts) < 2:
                self.send_error(404)
                return
            checksum = parts[1]
            subpath = parts[2] if len(parts) > 2 else "index.html"
            try:
                root = ensure_extracted(checksum)
            except Exception as e:
                self.send_error(500, f"extract failed: {e}")
                return
            file_path = os.path.join(root, subpath)
            if not os.path.isfile(file_path):
                self.send_error(404, f"not found: {subpath}")
                return
            # serve from the extracted directory with subpath resolution
            self.path = "/" + subpath
            self.directory = root
            # Cheap single-file serve since SimpleHTTPRequestHandler uses self.directory
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        self.send_error(404)

    def translate_path(self, path):
        # SimpleHTTPRequestHandler uses cwd; redirect to extracted app root
        if hasattr(self, "directory") and self.directory:
            return os.path.join(self.directory, path.lstrip("/"))
        return super().translate_path(path)

    def send_listing(self):
        body = [
            "<!doctype html><meta charset=utf-8><title>PraDigi HTML5 apps</title>",
            "<meta name=viewport content='width=device-width,initial-scale=1'>",
            "<style>body{font-family:system-ui;max-width:720px;margin:0 auto;padding:1em}"
            "li{margin:.4em 0;line-height:1.6}input{width:100%;padding:.5em;font-size:1em}</style>",
            f"<h1>PraDigi apps ({len(self.apps)})</h1>",
            "<input id=q placeholder='filter by title…' oninput='f()'>",
            "<ul id=list>",
        ]
        for node_id, title, checksum, lang in self.apps:
            safe_title = (
                title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            body.append(
                f'<li><a href="/app/{checksum}/index.html">{safe_title}</a> '
                f'<small>[{lang or "?"}]</small></li>'
            )
        body.append("</ul>")
        body.append(
            "<script>function f(){var q=document.getElementById('q').value.toLowerCase();"
            "document.querySelectorAll('#list li').forEach(function(li){"
            "li.style.display=li.textContent.toLowerCase().includes(q)?'':'none';})}</script>"
        )
        html = "".join(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    Handler.apps = list_html5_apps()
    ip = lan_ip()
    print(f"Serving {len(Handler.apps)} apps on:")
    print(f"  http://{ip}:{args.port}/       ← open this on your Android tablet")
    print(f"  http://localhost:{args.port}/  ← or here from desktop")
    print(f"extracting to {EXTRACT_ROOT}")

    # Allow LAN access
    class ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with ReusableServer(("0.0.0.0", args.port), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
