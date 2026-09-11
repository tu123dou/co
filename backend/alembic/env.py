from alembic import context
from sqlalchemy import create_engine, pool
from app.config import settings
from app.schema import metadata

config = context.config
if context.is_offline_mode():
    context.configure(
        url=settings().database_url,
        target_metadata=metadata,
        literal_binds=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(
        settings().database_url, poolclass=pool.NullPool
    ).connect() as connection:
        context.configure(
            connection=connection, target_metadata=metadata, include_schemas=True
        )
        with context.begin_transaction():
            context.run_migrations()
