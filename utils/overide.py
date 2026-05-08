from sqlalchemy import text

from utils.db import get_db_engine


def logging_stop_override(machine_id):
    try:
        with get_db_engine().connect() as connection:
            with connection.begin():  # Ensure transaction handling
                sql = text("""
                    UPDATE machine_list 
                    SET machine_status = 'active mould not running'
                    WHERE machine_code = :machine_code
                """)
                connection.execute(sql, {"machine_code": machine_id})  # Pass parameters as a dictionary
    except Exception as e:
        print(f"Error updating database: {e}")
