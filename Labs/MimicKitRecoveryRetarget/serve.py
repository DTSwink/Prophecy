"""Serve only the recovery review and shared read-only Three.js dependencies."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

FOLDER = Path(__file__).resolve().parent
VENDOR = FOLDER.parent / 'MimicKitUEFN/vendor'


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = unquote(urlsplit(path).path)
        if clean.startswith('/vendor/'):
            target = (VENDOR / clean.removeprefix('/vendor/')).resolve()
            if target.is_relative_to(VENDOR.resolve()):
                return str(target)
            return str(FOLDER / '__not_found__')
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8843), partial(Handler, directory=str(FOLDER))).serve_forever()
