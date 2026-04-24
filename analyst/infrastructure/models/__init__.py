"""SQLModel tables owned by the analyst service.

Importing this package registers every `XxxDB` class with
`SQLModel.metadata`, which is how Alembic autogenerate discovers them.
Add new aggregates here as they are introduced.
"""

from analyst.infrastructure.models.ticker import TickerDB

__all__ = ["TickerDB"]
