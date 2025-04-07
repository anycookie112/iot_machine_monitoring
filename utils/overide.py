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




   