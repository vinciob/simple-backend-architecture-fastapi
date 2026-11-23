"""Run periodically as an external scheduled job: python -m app.cleanup."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete

from app.core.config import DatabaseSettings
from app.core.database import create_engine
from app.modules.auth.models import Session
from app.modules.users.models import User  # noqa: F401


async def main() -> None:
    """Cleanup expired sessions from the database."""
    engine = create_engine(DatabaseSettings())
    try:
        async with engine.begin() as connection:
            # Foreign-key cascading removes the corresponding replay history as well.
            await connection.execute(delete(Session).where(Session.expires_at <= datetime.now(UTC)))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
