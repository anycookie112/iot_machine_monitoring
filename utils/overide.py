import dash_bootstrap_components as dbc
from dash import Input, Output, html, Dash, State, dash, dcc, callback_context, callback
from sqlalchemy import create_engine, text
import pandas as pd
import paho.mqtt.client as mqtt
import json
import threading
import time
import dash
from utils.efficiency import update_sql
from config.config import MQTT_CONFIG, DB_CONFIG
from utils.filter_mould import get_mould_list

"""
so for the iveride function
i need to send a message to python side 
the data i need will be 
 
"""

# Create engine once and reuse it
db_engine = create_engine(
    f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
)

def logging_stop_override(machine_id):
    try:
        with db_engine.connect() as connection:
            with connection.begin():  # Ensure transaction handling
                sql = text("""
                    UPDATE machine_list 
                    SET machine_status = 'active mould not running'
                    WHERE machine_code = :machine_code
                """)
                connection.execute(sql, {"machine_code": machine_id})  # Pass parameters as a dictionary
    except Exception as e:
        print(f"Error updating database: {e}")


# def logging_start_override(machine_id):
#     mqtt_machine = f"machines/{machine_id}"

#     try:
#         with db_engine.connect() as connection:
#             with connection.begin():  # Ensure transaction handling
#                 # Update machine status
#                 sql_update = text("""
#                     UPDATE machine_list 
#                     SET machine_status = 'mass prod'
#                     WHERE machine_code = :machine_code
#                 """)
#                 connection.execute(sql_update, {"machine_code": machine_id})

#                 # Fetch mould_id
#                 sql_query = text("""
#                     SELECT mould_id FROM machine_list 
#                     WHERE machine_code = :machine_code
#                 """)
#                 result = connection.execute(sql_query, {"machine_code": machine_id}).fetchone()

#                 if not result:
#                     print(f"Error: No mould_id found for machine_id {machine_id}")
#                     return  # Stop execution if no result

#                 mould_id = result[0]

#                 # Insert into mass_production table
#                 sql_insert = text("""
#                     INSERT INTO mass_production (machine_code, mould_id) 
#                     VALUES (:machine_code, :mould_id)
#                 """)
#                 result = connection.execute(sql_insert, {"machine_code": machine_id, "mould_id": mould_id})
#                 last_inserted_id = result.lastrowid

#                 # Fetch latest main_id from joblist
#                 sql_select = text("""
#                     SELECT main_id
#                     FROM joblist
#                     WHERE machine_code = :machine_code
#                     ORDER BY main_id DESC
#                     LIMIT 1
#                 """)
#                 result = connection.execute(sql_select, {"machine_code": machine_id}).fetchone()

#                 if not result:
#                     print(f"Error: No job found for machine_id {machine_id}")
#                     return  # Stop execution if no result

#                 main_id = result[0]

#                 # Publish MQTT message
#                 message = {
#                     "command": "start",
#                     "main_id": str(main_id),
#                     "mp_id": last_inserted_id
#                 }
#                 mqtt.publish(mqtt_machine, payload=json.dumps(message))

#     except Exception as e:
#         print(f"Error updating database: {e}")



   