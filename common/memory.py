"""Memory management utilities for Oraculum Harvester."""

from __future__ import annotations

import ctypes
import gc
import logging

logger = logging.getLogger(__name__)


def release_memory() -> None:
    """Force garbage collection and trim the malloc heap.
    
    Particularly useful in Linux container environments (like Docker or k3s pods)
    after processing large datasets (Pandas, Pydantic) to return memory to the OS.
    """
    # 1. Force Python garbage collection
    collected = gc.collect()
    logger.debug("Garbage collection completed. Reclaimed %d objects.", collected)

    # 2. Reclaim memory pages from C heap allocator (glibc only)
    try:
        # libc.so.6 is the standard glibc library on Linux
        libc = ctypes.CDLL("libc.so.6")
        # malloc_trim(0) releases all possible free memory from the heap back to the OS
        res = libc.malloc_trim(0)
        logger.debug("malloc_trim(0) returned: %d", res)
    except (OSError, AttributeError) as e:
        logger.debug("malloc_trim is not available or supported on this platform: %s", e)
