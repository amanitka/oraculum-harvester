"""Abstract base class for Parquet merge strategies."""

from __future__ import annotations

import abc
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession


class ParquetMergeStrategy(abc.ABC):
    """Defines the contract for merging a dataset into a target table."""

    @abc.abstractmethod
    async def merge(
        self,
        session: AsyncSession,
        stg_table: str,
        records: list[dict[str, Any]],
    ) -> None:
        """
        Create a staging table, load data, and merge into the final table.

        Args:
            session: The active SQLAlchemy async session.
            stg_table: The name to use for the temporary staging table.
            records: A list of dictionaries representing the rows to load.
        """
        raise NotImplementedError
