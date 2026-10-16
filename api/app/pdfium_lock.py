"""pdfium (pypdfium2) must never run in two threads at once, even on different documents.

Every function that touches pdfium runs under this one lock: notes indexing (NR), reading a
question photo/PDF (C2) and /pdf/read (TE, PY) all parse in worker threads.
"""

import threading
from collections.abc import Callable
from functools import wraps

_LOCK = threading.Lock()


def one_at_a_time[**P, R](f: Callable[P, R]) -> Callable[P, R]:
    @wraps(f)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        with _LOCK:
            return f(*args, **kwargs)
    return run
