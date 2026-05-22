import asyncio
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine


class TestLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: str


engine = create_async_engine("sqlite+aiosqlite:///:memory:")


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session = AsyncSession(engine)
    log = TestLog(status="RUNNING")
    session.add(log)
    await session.commit()
    await session.refresh(log)

    try:
        # Simulate error
        await session.exec(
            select(TestLog).where(TestLog.id == "invalid")
        )  # this might not error in sqlite, let's do something else
        raise ValueError("Simulated error")
    except Exception:
        await session.rollback()
        log.status = "FAILED"
    finally:
        session.add(log)
        await session.commit()

    await session.refresh(log)
    print(log.status)


if __name__ == "__main__":
    asyncio.run(main())
