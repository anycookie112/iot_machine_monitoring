from functools import lru_cache

from sqlalchemy import create_engine

from config.config import DB_CONFIG, DB_URL


def get_db_url():
    if DB_URL:
        return DB_URL

    missing = [
        env_name
        for env_name, value in (
            ("MM_DB_USERNAME", DB_CONFIG["username"]),
            ("MM_DB_PASSWORD", DB_CONFIG["password"]),
            ("MM_DB_HOST", DB_CONFIG["host"]),
            ("MM_DB_NAME", DB_CONFIG["database"]),
        )
        if not value
    ]

    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Database configuration is incomplete. Set MM_DB_URL or the following "
            f"environment variables: {joined}"
        )

    return (
        f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    )


@lru_cache(maxsize=1)
def get_db_engine():
    return create_engine(
        get_db_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_raw_connection():
    return get_db_engine().raw_connection()
