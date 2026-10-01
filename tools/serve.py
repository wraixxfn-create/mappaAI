#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serve.py — server statico minimo per il viewer del modello 3D.

Serve la cartella radice del progetto (così il viewer può caricare
../models/frullatore.glb) e si aggancia a 0.0.0.0 per essere raggiungibile
anche da ambienti con preview remota.

Uso:
    python3 tools/serve.py [porta]     # default 8000
"""

from __future__ import annotations

import functools
import http.server
import mimetypes
import socket
import socketserver
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    """Handler con MIME corretti per i file del modello e log essenziale."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, formato: str, *args) -> None:  # noqa: A003
        if "/node_modules/" not in self.path:
            sys.stderr.write("  %s\n" % (formato % args))

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/viewer/")
            self.end_headers()
            return
        super().do_GET()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def indirizzo_locale() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    mimetypes.add_type("model/gltf-binary", ".glb")
    mimetypes.add_type("model/gltf+json", ".gltf")
    mimetypes.add_type("application/javascript", ".js")

    handler = functools.partial(Handler, directory=str(RADICE))
    with Server(("0.0.0.0", porta), handler) as httpd:
        print(f"Viewer del frullatore → http://localhost:{porta}/viewer/")
        print(f"                        http://{indirizzo_locale()}:{porta}/viewer/")
        print("Ctrl+C per terminare.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer arrestato.")


if __name__ == "__main__":
    main()
