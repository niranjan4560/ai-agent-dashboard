from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()


def _normalise_url(url: str) -> str:
    # Render/Heroku/Neon dashboards often hand out postgres:// URLs, which
    # SQLAlchemy 2 no longer accepts.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # The installed driver is psycopg 3 (SQLAlchemy 2.1's default for postgresql://).
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
    return url


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and point it at a "
        "PostgreSQL database (e.g. a free Neon instance)."
    )

DATABASE_URL = _normalise_url(DATABASE_URL)

_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    # Used by the test-suite; FastAPI runs handlers in a thread pool.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Managed Postgres (Neon, Render) closes idle connections — check before use.
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5)

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
