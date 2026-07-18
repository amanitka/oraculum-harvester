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
    # 1. Clear functools.lru_cache across imported modules to release cached objects (e.g. from edgartools)
    import sys
    for name, module in list(sys.modules.items()):
        if module and (name.startswith("edgar") or name.startswith("pandas") or name.startswith("pyarrow") or name.startswith("simfin")):
            for attr_name in dir(module):
                try:
                    attr = getattr(module, attr_name)
                    if hasattr(attr, "cache_clear") and callable(attr.cache_clear):
                        attr.cache_clear()
                except Exception:
                    pass

    # 2. Force Python garbage collection
    collected = gc.collect()
    logger.debug("Garbage collection completed. Reclaimed %d objects.", collected)

    # 3. Reclaim memory from PyArrow default and system memory pools
    try:
        import pyarrow
        pyarrow.default_memory_pool().release_unused()
        pyarrow.system_memory_pool().release_unused()
        logger.debug("PyArrow memory pools released.")
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Failed to release PyArrow memory pools: %s", e)

    # 4. Reclaim memory pages from C heap allocator (glibc only)
    try:
        # libc.so.6 is the standard glibc library on Linux
        libc = ctypes.CDLL("libc.so.6")
        # malloc_trim(0) releases all possible free memory from the heap back to the OS
        res = libc.malloc_trim(0)
        logger.debug("malloc_trim(0) returned: %d", res)
    except (OSError, AttributeError) as e:
        logger.debug("malloc_trim is not available or supported on this platform: %s", e)
