from logging.config import fileConfig
import asyncio
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from app.core import settings
from app.db import Base

from app.modules.users.models import User
from app.modules.user_settings.models import UserSettings
from app.modules.weight_history.models import WeightHistory
from app.modules.database_foods.models import DatabaseFoods
from app.modules.nutrients.models import Nutrient
from app.modules.food_nutrients.models import FoodNutrient
from app.modules.user_plans.models import UserPlan
from app.modules.daily_logs.models import DailyLog
from app.modules.logged_foods.models import LoggedFood

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def do_run_migrations(connection):
    """Hàm thực thi migration đồng bộ bên trong kết nối async"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """Tạo Engine Async và chạy migration"""

    url = settings.DATABASE_URL

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    asyncio.run(run_async_migrations())
    # configuration = config.get_section(config.config_ini_section, {})

    # configuration["sqlalchemy.url"] = settings.DATABASE_URL

    # connectable = engine_from_config(
    #     configuration,
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    # with connectable.connect() as connection:
    #     context.configure(
    #         connection=connection, target_metadata=target_metadata, compare_type=True
    #     )

    #     with context.begin_transaction():
    #         context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
