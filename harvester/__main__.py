"""`python -m harvester` entry point.

Equivalent to `faststream run harvester.app:app`; both are valid. The
custom entry point keeps logging configuration in one place and avoids a
CLI dependency for simple deployments.
"""

from __future__ import annotations

import asyncio
import logging

from harvester.app import app

logger = logging.getLogger(__name__)


async def _run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutting down harvester")
