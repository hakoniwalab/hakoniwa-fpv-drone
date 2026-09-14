#!/usr/bin/env python3
"""Serve the static FPV Browser Composer and pre-generated Catalog assets."""
from __future__ import annotations

import argparse
import http.server
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ComposerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve Composer sources without caching during iterative local demos."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the FPV Browser Composer.")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--open", action="store_true", help="open the Composer in the default browser")
    args = parser.parse_args()
    assets = ROOT / "build" / "catalog-showroom" / "glb" / "assembly-contract.json"
    if not assets.is_file():
        parser.error("Catalog assets are missing; run: python3 tools/fpv-catalog.py export-glb")
    url = f"http://{args.host}:{args.port}/composer/"
    server = http.server.ThreadingHTTPServer(
        (args.host, args.port),
        lambda *a, **kw: ComposerRequestHandler(*a, directory=str(ROOT), **kw),
    )
    print(f"FPV Composer: {url}")
    if args.open:
        webbrowser.open(url, new=2)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
