from logging.config import fileConfig
from urllib.parse import quote_plus
import os

from dotenv import load_dotenv
from sqlalchemy import pool, create_engine
from alembic import context

from src.database import Base
import src.admin.model
import src.atividade.model
import src.banda_palestrante.model
import src.drive.model
import src.evento.model
import src.produto.model
import src.voluntario.models
import src.lider.model
import src.participante.models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv(".env", override=True)

x_env = context.get_x_argument(as_dictionary=True).get("env", "local")

if x_env == "prod":
    user = quote_plus(os.environ.get("SUPABASE_USER", ""))
    password = quote_plus(os.environ.get("SUPABASE_PASSWORD", "").strip())
    host = os.environ.get("SUPABASE_HOST", "")
    port = os.environ.get("SUPABASE_PORT", "5432")
    db = os.environ.get("SUPABASE_DB", "")
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"
else:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()