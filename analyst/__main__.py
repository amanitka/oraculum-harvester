"""`python -m analyst` entry point.

Equivalent to `faststream run analyst.app:app`; both are valid. The
custom entry point keeps logging + engine shutdown in one place and
avoids a CLI dependency for simple deployments.
"""

from __future__ import annotations

import asyncio
import logging

from analyst.app import app
from analyst.infrastructure.engine import EngineProvider

logger = logging.getLogger(__name__)


async def _run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        await app.run()
    finally:
        await EngineProvider.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutting down analyst consumer")
