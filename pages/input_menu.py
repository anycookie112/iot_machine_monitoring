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
from utils.overide import logging_stop_override
from utils.mqtt import publish_message
from utils.timer import Timer, TimerNew, toggle_machine_timer

t = Timer()
t_adjust = Timer()

db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
db_connection = create_engine(db_connection_str)

df = pd.read_sql(f'''
    SELECT * FROM machine_list
''', con=db_connection)
# Initialize the Dash app
# app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
dash.register_page(__name__, path="/")
machines = []

for index, row in df.iterrows():
    machines.append(row)

mould_code_select = get_mould_list()
"""
so if i want to disable the moulds that are already in use (i can just add a true/false column)
i need to append the data into a dict
if mould = active disable = true
for idx, 
machine{
    value:
    disable
    }
{"value": mould1, "disabled": true/false}
(Not done)
"""
df_mould = pd.read_sql(f'''
    SELECT * FROM mould_list
''', con=db_connection)


for index, row in df_mould.iterrows():
    mould_code_select.append(row["mould_code"])

inline_checklist = html.Div(
    [
        dbc.Label("Customer"),
        dbc.RadioItems(
            options=[
                {"label": "Panasonic", "value": 'panasonic'},
                {"label": "HEM", "value": 'hem'},
                {"label": "Hfuji", "value": 'hfuji'},
                {"label": "Yamada", "value": 'yamada'},
                {"label": "Osaka", "value": 'osaka'},
                {"label": "SMK", "value": 'smk'},
                {"label": "UD", "value": 'ud'},
            ],
            value=[],
            id="checklist-inline-input",
            inline=True,
        ),
    ]
)

# All items in this list will have the value the same as the label
select = html.Div(
    dbc.Select(
        mould_code_select,
        id="shorthand-select",
    ),
    className="py-2",
)

short_hand = html.Div(
    [
        dbc.Form([select]),
        html.P(id="shorthand-output"),
    ]
)


dash.register_page(__name__, path='/')

layout = html.Div([

    dbc.Alert(
            "Adjustment/ QA-QC in progress",
            id="alert-auto",
            is_open=False,
            duration=4000,
        ),
    dbc.Alert(
            "Downmould progress start",
            id="alert-auto-dm",
            is_open=False,
            duration=4000,
        ),
    dbc.Alert(
            "Start Logging Data",
            id="alert-auto-on",
            is_open=False,
            duration=4000,
        ),

    dbc.Card(
    [
        dbc.CardBody(
            [
                html.H1("PRODUCTION MONITORING", className="text-center mb-4"),
                dcc.Dropdown(
                    ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8','A10', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'],

                    value='A1', 
                    id='machine_id', 
                    className="mb-4"
                ),
                html.P(id="status", children="Status: Test", className="card-text mb-2"),
                html.P(id="mould", children="Active Mould: Test", className="card-text mb-4"),

                dbc.Row(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("PRODUCTION START", id="on", n_clicks=0, color="success" , className="btn btn-primary me-2 mb-2"),
                            dbc.Button("PRODUCTION STOP", id="off", n_clicks=0, color="danger", className="btn btn-primary me-2 mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),

                dbc.Row(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Mould Change Start", id="ums", n_clicks=0, className="btn btn-primary me-2 mb-2"),
                        dbc.Button("Mould Change End", id="ume", n_clicks=0, color="danger", className="btn btn-primary mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),

                dbc.Row(
                    dbc.ButtonGroup(
                        [
                          dbc.Button("Adjustment", id="qas", n_clicks=0, className="btn btn-primary me-2 mb-2"),
                        dbc.Button("Adjustment", id="qae", n_clicks=0, color="danger", className="btn btn-primary mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),

                dcc.Interval(id="refresh", n_intervals=-1),
            ]
        ),
    ],
    className="m-2",
),
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header")),
                dbc.ModalBody([
                               inline_checklist,
                                short_hand
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Close", id="close",  n_clicks=0),
                    dbc.Button("OK", color="primary", id="ok", className="ms-auto", n_clicks=0),
                ]),
            ],
            id="modal",
            is_open=False
        )
    ]),
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header")),
                dbc.ModalBody([
                               "Confirm complete?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-1",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-1", className="ms-auto", n_clicks=0),
                ]),
            ],
            id="confirmation-1",
            is_open=False,
        )
    ]),
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header")),
                dbc.ModalBody([
                               "Confirm complete?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-2",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-2", className="ms-auto", n_clicks=0),
                    dbc.Input(id="name", placeholder="Name", type="text"),
                ]),
            ],
            id="confirmation-2",
            is_open=False,
        )
    ]),
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header")),
                dbc.ModalBody([
                               "Confirm complete?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-3",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-3", className="ms-auto", n_clicks=0),
                ]),
            ],
            id="confirmation-3",
            is_open=False,
        )
    ]), 
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Header")),
                dbc.ModalBody([
                               "Confirm complete?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-4",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-4", className="ms-auto", n_clicks=0),
                ]),
            ],
            id="confirmation-4",
            is_open=False,
        )
    ]),   
    

])

@callback(
    [
    #machine and mould status
    Output('status', 'children'),
    Output('mould', 'children'),
    #start buttons
    Output('on', 'disabled'),
    Output('ums', 'disabled'),
    # Output('dms', 'disabled'),
    Output('qas', 'disabled'),
    #stop buttons
    Output('off', 'disabled'),
    Output('ume', 'disabled'),
    # Output('dme', 'disabled'),
    Output('qae', 'disabled'),
    ],
    [
    Input("machine_id", "value"), Input("refresh", 'n_intervals')
    ]
)

def update_output(value, n):
    df = pd.read_sql("SELECT * FROM machine_list", con=db_connection)
    filtered_df = df[df["machine_code"] == value]

    mould_id = filtered_df["mould_id"].iloc[0]
    status = filtered_df["machine_status"].iloc[0]
    # Disabled by default
    button_state_on = True  
    button_state_ums = True 
    # button_state_dms = True
    button_state_qas = True

    button_state_off = True  
    button_state_ume = True
    # button_state_dme = True
    button_state_qae = True

    if status == "off":
        # no active mould on machine, only available option is up a new mould
        button_state_ums = False  
 
    elif status == "change mould in progress":
        # active mould but no other actions
        button_state_ume = False

    elif status == "active mould not running":
        button_state_on = False 
        button_state_ums = False  
        # button_state_dms = False
        button_state_qas = False

    elif status == "adjustment/qa in progress":
        button_state_qae = False

    elif status == "mass prod":
        button_state_off = False  

    return f"Status: {status}", f"Active Mould: {mould_id}", button_state_on, button_state_ums, button_state_qas, button_state_off, button_state_ume, button_state_qae


"""

UP MOULD

"""

@callback(
    Output("modal", "is_open"),
    [Input("ums", "n_clicks"), Input("close", "n_clicks"), Input("ok", "n_clicks"), Input('shorthand-select', 'value')],
    [State("modal", "is_open"), State("machine_id", "value")]
)
def change_mould_start(ums, close, ok, mould_id,  is_open, machine_id):
    # Identify which input triggered the callback
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None

    # Handle "UMS" button click
    if triggered_id == "ums":
        return not is_open

    # Handle "Close" button click
    if triggered_id == "close":
        return False  # Close the modal

    # Handle "OK" button click
    if triggered_id == "ok":
        if not mould_id or not mould_id.strip():
            # If name is empty or just whitespace, do nothing (keep modal open)
            return True
        try:
            toggle_machine_timer(machine_id)
            # Database update
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = "UPDATE machine_list SET mould_id = %s, machine_status = 'change mould in progress' WHERE machine_code = %s"
                cursor.execute(sql, (str(mould_id), str(machine_id)))

                sql_insert = "INSERT INTO joblist (machine_code, mould_code, time_input) VALUES (%s, %s, NOW())"
                cursor.execute(sql_insert, (str(machine_id), str(mould_id)))
                connection.commit()

                message = json.dumps({"command": "ums"})
                publish_message(mqtt_machine, message, qos=2)  

        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            connection.close()
        return False  # Close the modal after successful action

    # Default case: No button was clicked
    return is_open

@callback(
    Output("confirmation-1", "is_open"),
    [Input("ume", "n_clicks"), Input("yes-1", "n_clicks"), Input("no-1", "n_clicks")],
    [State("confirmation-1", "is_open"), State("machine_id", "value")]
)
def change_mould_end(ume, yes, no, is_open, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
   
    # When "ume" is clicked, open the modal
    if triggered_id == "ume":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-1":
        try:
            elasped_time = toggle_machine_timer(machine_id)
            # Connect to the database
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                # Update the machine status
                sql_update = """
                UPDATE machine_list 
                SET machine_status = 'active mould not running'
                WHERE machine_code = %s
                """
                cursor.execute(sql_update, (machine_id,))  # Pass as a single-element tuple

                # Fetch the most recent entry from joblist
                sql_select = """
                SELECT main_id
                FROM joblist
                WHERE machine_code = %s
                ORDER BY main_id DESC
                LIMIT 1
                """
                cursor.execute(sql_select, (str(machine_id),))
                result = cursor.fetchone()

                if result:
                    main_id = result[0]
                    sql_insert = """
                    INSERT INTO monitoring (main_id, action, time_taken, time_input)
                    VALUES (%s, "change mould", %s, NOW())
                    """
                    cursor.execute(sql_insert, (str(main_id), elasped_time,))
                    connection.commit()

                    
                    message = json.dumps({"command": "ume"})
                    publish_message(mqtt_machine, message, qos=2)  

                else:
                    print(f"No matching entry found in joblist for machine_id {machine_id}")

                connection.commit()  # Commit the transaction


        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            connection.close()

        return False  # Close modal after action

    # When "no" is clicked, just close the modal without any action
    if triggered_id == "no-1":
        return False  # Close modal

    # Default: Return current modal state if no input is triggered
    return is_open



"""

ADJUSTMENT/ QA-QC

"""

@callback(
    Output("alert-auto", "is_open"),
    [Input("qas", "n_clicks")],
    [State("alert-auto", "is_open"), State("machine_id", "value")]
)
def adjustment(qas, alert, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    # Check if the callback was triggered by the "qas" button
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    if triggered_id != "qas":
        # If not triggered by the button, do nothing (retain current state)
        return dash.no_update

    # Proceed with updating the database if "qas" was clicked
    try:
        connection = create_engine(db_connection_str).raw_connection()
        with connection.cursor() as cursor:
            sql = """
            UPDATE machine_list 
            SET machine_status = 'adjustment/qa in progress'
            WHERE machine_code = %s
            """
            cursor.execute(sql, (str(machine_id),))
            connection.commit()
            toggle_machine_timer(machine_id)


            message = json.dumps({"command": "qas"})
            publish_message(mqtt_machine, message, qos=2)  

            return True  # Show the alert
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        connection.close()

    return dash.no_update

@callback(
    Output("confirmation-2", "is_open"),
    [Input("qae", "n_clicks"), Input("yes-2", "n_clicks"), Input("no-2", "n_clicks"), Input("name", "value")],
    [State("confirmation-2", "is_open"), State("machine_id", "value")]
)
def adjustment_end(ume, yes, no, name, is_open, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    # When "ume" is clicked, open the modal
    if triggered_id == "qae":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-2":
        if not name or not name.strip():
            # If name is empty or just whitespace, do nothing (keep modal open)
            return True
        
        try:
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = """
                UPDATE machine_list 
                SET machine_status = 'active mould not running'
                WHERE machine_code = %s
                """
                cursor.execute(sql, (str(machine_id),))
                connection.commit()
            
            # Fetch the most recent entry from joblist
                sql_select = """
                SELECT main_id
                FROM joblist
                WHERE machine_code = %s
                ORDER BY main_id DESC
                LIMIT 1
                """
                cursor.execute(sql_select, (str(machine_id),))
                result = cursor.fetchone()

                if result:
                    main_id = result[0]
                    elasped_time = toggle_machine_timer(machine_id)

                    sql_insert = """
                    INSERT INTO monitoring (main_id, action, time_taken, time_input, remarks)
                    VALUES (%s, "adjustment", %s, NOW(), %s)
                    """
                    cursor.execute(sql_insert, (str(main_id), elasped_time, name,))
                    connection.commit()

                    message = json.dumps({"command": "qas"})
                    publish_message(mqtt_machine, message, qos=2)  



        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            connection.close()
        return False  # Close modal after action

    # When "no" is clicked, just close the modal without any action
    if triggered_id == "no-2":
        return False  # Close modal

    # Default: Return current modal state if no input is triggered
    return is_open



"""

START/STOP LOGGING DATA

"""



@callback(
    Output("alert-auto-on", "is_open"),
    [Input("on", "n_clicks")],
    [State("alert-auto-on", "is_open"), State("machine_id", "value")]
)
def logging_start(on, alert, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    # Check if the callback was triggered by the "qas" button
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    if triggered_id != "on":
        # If not triggered by the button, do nothing (retain current state)
        return dash.no_update

    # Proceed with updating the database if "qas" was clicked
    try:
        connection = create_engine(db_connection_str).raw_connection()
        with connection.cursor() as cursor:
            sql = """
            UPDATE machine_list 
            SET machine_status = 'mass prod'
            WHERE machine_code = %s
            """
            cursor.execute(sql, (str(machine_id),))

            sql_query = """
            select mould_id from machine_list 
            where machine_code = %s
            """
            cursor.execute(sql_query, (str(machine_id),))
            result = cursor.fetchone()

            if result:
                mould_id = result[0]
                # print(mould_id)

            sql_insert = " INSERT INTO mass_production (machine_code, mould_id) VALUES (%s, %s)"
            cursor.execute(sql_insert, (str(machine_id), str(mould_id)))
            last_inserted_id = cursor.lastrowid

            sql_select = """
                SELECT main_id
                FROM joblist
                WHERE machine_code = %s
                ORDER BY main_id DESC
                LIMIT 1
                """
            cursor.execute(sql_select, (str(machine_id),))
            result = cursor.fetchone()

            if result:
                main_id = result[0]
                message = {
                        "command": "start",
                        "main_id": str(main_id),
                        "mp_id": last_inserted_id
                    }
                # mqttc.publish(mqtt_machine, payload=json.dumps(message))
                publish_message(mqtt_machine, payload=json.dumps(message), qos=2)            

            connection.commit() 
            return True  # Show the alert
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        connection.close()

    return dash.no_update

"""
insert new row into mass_production
insert machine_code
get last inserted id
send the last inserted_id along with the command "start" to the esp32 to signal can start logging data

"""

@callback(
    Output("confirmation-4", "is_open"),
    [Input("off", "n_clicks"), Input("yes-4", "n_clicks"), Input("no-4", "n_clicks")],
    [State("confirmation-4", "is_open"), State("machine_id", "value")]
)
def logging_stop(dme, yes, no, is_open, machine_id):
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    mqtt_machine = f"machines/{machine_id}"
    # When "ume" is clicked, open the modal
    if triggered_id == "off":

        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-4":
        try:
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = """
                UPDATE machine_list 
                SET machine_status = 'active mould not running'
                WHERE machine_code = %s
                """
                cursor.execute(sql, (str(machine_id),))
                connection.commit()

                message = {"command": "stop", }
                # mqttc.publish(mqtt_machine, payload=json.dumps(message))
                publish_message(mqtt_machine, payload=json.dumps(message), qos=2)
        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            connection.close()
        return False  # Close modal after action

    # When "no" is clicked, just close the modal without any action
    if triggered_id == "no-4":
        return False  # Close modal

    # Default: Return current modal state if no input is triggered
    return is_open


@callback(
    Output('shorthand-select', 'options'),
    Input('checklist-inline-input', 'value')
)

def mould_filter(customer):
    updated_list = get_mould_list(customer)
    return updated_list
    
