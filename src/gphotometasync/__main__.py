"""Start the local server and open the app in the browser.

Used by `python -m gphotometasync`, the `gphotometasync` script and the desktop bundles
(PyInstaller runs this file as a script, hence the absolute imports).
"""

import os
import sys
import threading
import webbrowser

from werkzeug.serving import make_server

from gphotometasync.log import get_logger
from gphotometasync.web.app import create_app

logger = get_logger(__name__)


def main() -> None:
    app = create_app()
    # Use a stable development port, but avoid collisions in a frozen desktop app.
    default_port = "0" if getattr(sys, "frozen", False) else "5001"
    port = int(os.environ.get("PORT", default_port))
    # Threaded, so a long export or a pending Google sign-in doesn't freeze the UI.
    server = make_server("127.0.0.1", port, app, threaded=True)
    url = f"http://127.0.0.1:{server.server_port}"
    logger.info("Photo Meta Sync is running at {}", url)
    threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Photo Meta Sync stopped")


if __name__ == "__main__":
    main()
