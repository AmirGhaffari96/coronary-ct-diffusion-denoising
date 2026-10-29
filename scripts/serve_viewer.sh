#!/usr/bin/env bash
# Serve the coronary denoising viewer on http://localhost:8712 (threaded, for
# the ~800-image-per-case preload the viewer does on load).
#
# Loopback-only by design: these are patient images and there is no auth here.
# Reach it from elsewhere with  ssh -L 8712:localhost:8712 <user>@<host>
cd "$(dirname "$0")/../viewer" || exit 1
exec "/mnt/raid2/amirg/Diff Models/envs/diffct/bin/python" - "$@" <<'PY'
import http.server, socketserver

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class Handler(http.server.SimpleHTTPRequestHandler):
    """Never let the browser cache index.html or the manifests.

    Without this, editing the viewer and reloading shows the OLD page: the
    default handler answers If-Modified-Since with a 304 and the browser keeps
    serving its cached copy. The baked slices are immutable and large, so they
    are deliberately left cacheable.
    """
    def end_headers(self):
        path = self.path.split('?')[0]
        if path.endswith(('.html', '.json')) or path.endswith('/'):
            self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

with ThreadingHTTPServer(("127.0.0.1", 8712), Handler) as httpd:
    httpd.serve_forever()
PY
