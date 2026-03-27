import os
import sys

from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.config import DB_CONFIG


DB_URL = (
    f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
)

INDEX_STATEMENTS = {
    "idx_monitoring_time_mp": "CREATE INDEX idx_monitoring_time_mp ON monitoring (time_input, mp_id)",
    "idx_monitoring_action_time_mp_main": (
        "CREATE INDEX idx_monitoring_action_time_mp_main "
        "ON monitoring (action, time_input, mp_id, main_id)"
    ),
    "idx_monitoring_mp_time_action": (
        "CREATE INDEX idx_monitoring_mp_time_action "
        "ON monitoring (mp_id, time_input, action)"
    ),
}


def main():
    engine = create_engine(DB_URL)

    with engine.begin() as connection:
        existing_indexes = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT index_name
                    FROM information_schema.statistics
                    WHERE table_schema = :schema_name
                    AND table_name = 'monitoring'
                    """
                ),
                {"schema_name": DB_CONFIG["database"]},
            )
        }

        for index_name, statement in INDEX_STATEMENTS.items():
            if index_name in existing_indexes:
                print(f"{index_name}: already exists")
                continue

            print(f"{index_name}: creating")
            connection.execute(text(statement))
            print(f"{index_name}: created")


if __name__ == "__main__":
    main()
