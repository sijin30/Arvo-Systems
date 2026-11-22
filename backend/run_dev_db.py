"""Start a throw-away local PostgreSQL for development (no installation needed).

    python run_dev_db.py            # prints DATABASE_URL, then keeps the server running

Data is kept in backend/.pgdev (git-ignored).  Press Ctrl+C to stop.
"""
from pathlib import Path
import time

import pgserver

server = pgserver.get_server(Path(__file__).resolve().parent / ".pgdev", cleanup_mode="stop")
print("DATABASE_URL=" + server.get_uri(), flush=True)
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    pass
finally:
    server.cleanup()
