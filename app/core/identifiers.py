"""Keep the public 24-hex identifier format independent of database technology."""

import secrets
import time


def new_id() -> str:
    """Generate a new unique 24-hex identifier.

    The identifier consists of a time-based prefix for approximate chronological ordering
    and a random suffix to avoid collisions across different workers.
    """
    # Time prefix supports keyset pagination; random suffix avoids cross-worker collisions.
    # IDs are approximately chronological, not a globally synchronized sequence.
    return f"{time.time_ns():016x}{secrets.token_hex(4)}"
