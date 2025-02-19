import dash_bootstrap_components as dbc
from dash import Input, Output, html, Dash, State, dash, dcc, callback_context, callback
from sqlalchemy import create_engine
import pandas as pd
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import uuid
import threading
import time
import dash
from utils.efficiency import update_sql

db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
db_connection = create_engine(db_connection_str)

df = pd.read_sql(f'''
    SELECT * FROM machine_list
''', con=db_connection)
# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

machines = []

for index, row in df.iterrows():
    machines.append(row)

mould_list = []
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
    SELECT * FROM mould_masterlist
''', con=db_connection)


for index, row in df_mould.iterrows():
    mould_list.append(row["mould_code"])

machine_id = "A3"
mqtt_broker = "192.168.1.15"
# mqtt_broker = "192.168.0.31"
mqtt_port = 1883
# mqtt_topic_cycle_time = "machine/cycle_time"
# mqtt_topic_status = "machine/status"
# mqtt_topic_publish = "machine/checking"
mqtt_topic_ums = "machine/ums"
topic = "status/+"  # Subscribe to all machine status topics


# mqtt_machine = f"machines/{machine_id}"


# Initialize MQTT client
mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Updated callbacks for new API
def on_connect(client, userdata, flags, reason_code, properties):
    # print(f"Connected with result code {reason_code}")
    client.subscribe(topic)
    client.subscribe("machine/+")  # Subscribe to direct child topics

# def on_disconnect(client, userdata, rc, properties=None):
def on_disconnect(client, userdata, flags, reason_code, properties):
    """Callback for when the client disconnects from the broker."""
    if reason_code != 0:
        print("Unexpected disconnection. Attempting to reconnect...")
        retry_interval = 5  # Start with 5 seconds
        while True:
            try:
                client.reconnect()
                print("Reconnected to MQTT broker.")
                break
            except Exception as e:
                print(f"Reconnection failed: {e}. Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
                retry_interval = min(retry_interval * 2, 60)  # Exponential backoff (up to 60 seconds)

def on_message(client, userdata, msg):
    """Callback for handling received messages."""
    try:
        # Decode the message payload
        payload = msg.payload.decode()
        print(payload)
        if msg.topic.startswith("status/"):
            # Parse the message into a JSON object
            message_data = json.loads(payload)

            # Get the machine status and machine ID
            status = message_data.get("status")
            machine_id = message_data.get("machineid")
            mqtt_machine = f"machines/{machine_id}"
            # print(status)
            # print(machine_id)

            if status and machine_id:
                # Create a database connection
                connection = create_engine(db_connection_str).raw_connection()
                with connection.cursor() as cursor:
                    sql = "UPDATE machine_list SET esp_status = %s WHERE machine_code = %s"
                    cursor.execute(sql, (status, machine_id))
                    connection.commit()

                    sql_status = "SELECT machine_status FROM machine_list WHERE machine_code = %s"
                    cursor.execute(sql_status, (machine_id,))
                    result_status = cursor.fetchone()

                    # print(machine_status)
                    if result_status:  # Check if a result was found
                        machine_status = result_status[0]  # Extract status from the fetched row
                        
                        if machine_status == "mass prod":
                            sql_select = """
                            SELECT main_id
                            FROM joblist
                            WHERE machine_code = %s
                            ORDER BY main_id DESC
                            LIMIT 1
                            """
                            cursor.execute(sql_select, (str(machine_id),))
                            result_mainid = cursor.fetchone()
                            main_id = result_mainid[0]
                            print(result_mainid)

                            sql_select = """
                            SELECT mp_id
                            FROM mass_production
                            WHERE machine_code = %s
                            ORDER BY mp_id DESC
                            LIMIT 1
                            """
                            cursor.execute(sql_select, (str(machine_id),))
                            result_mpid = cursor.fetchone()
                            mp_id = result_mpid[0]
                            message = {
                                "command": "true",
                                "mp_id": str(mp_id),
                                "main_id": str(main_id)
                            }
                            client.publish(mqtt_machine, payload=json.dumps(message))


                    print(f"Updated status for {machine_id} to {status}")

        if msg.topic.startswith("machine/"):
            message_data = json.loads(payload)

            # Get the machine status and machine ID
            mp_id = message_data.get("mp_id")
            print(mp_id)
            # machine_id = message_data.get("machineid")
            # mqtt_machine = f"machines/{machine_id}"
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = """            
                SELECT 
                m.mp_id, 
                mm.mould_code,
                mm.total_shot_count,
                mm.next_service_shot_count,
                COUNT(*) AS row_count
                FROM monitoring AS m
                JOIN joblist AS j ON m.main_id = j.main_id
                JOIN mould_masterlist AS mm ON j.mould_code = mm.mould_code
                WHERE m.mp_id = %s
                GROUP BY m.mp_id, mm.mould_code, mm.total_shot_count, mm.next_service_shot_count

                    """
                cursor.execute(sql, (str(mp_id),))
                results = cursor.fetchall()
                for row in results:
                    mould_code = row[1]  
                    tsc = row[2]
                    nssc = row[3]
                    row_count = row[4]  
                """
                i need to + row count first before comparing
                so tsc + row_count >= nssc
                update accordingly
                """



                tsc = tsc + row_count
                if tsc >= nssc:
                    sql_update = """
                    update mould_masterlist set total_shot_count = total_shot_count + %s, service_status = 1 where mould_code = %s
                    """
                    cursor.execute(sql_update, (row_count, str(mould_code),))
                    connection.commit()
                else:
                    sql_update = """
                    update mould_masterlist set total_shot_count = total_shot_count + %s where mould_code = %s
                    """
                    cursor.execute(sql_update, (row_count, str(mould_code),))
                    connection.commit()

            update_sql(mp_id, complete=True)

    except Exception as e:
        print(f"Error processing message: {e}")

# Assign callbacks
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect
mqttc.on_message = on_message

# Function to start MQTT loop
def mqtt_loop():
    mqttc.connect(mqtt_broker, mqtt_port, 60)
    mqttc.loop_forever()

# Run MQTT loop in a separate thread
mqtt_thread = threading.Thread(target=mqtt_loop, daemon=True)
mqtt_thread.start()



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
                html.H1("IoT Machine Status Dashboard", className="text-center mb-4"),
                dcc.Dropdown(
                    ['A8'], 
                    value='A8', 
                    id='machine_id', 
                    className="mb-4"
                ),
                html.P(id="status", children="Status: Test", className="card-text mb-2"),
                html.P(id="mould", children="Active Mould: Test", className="card-text mb-4"),

                dbc.Row(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("ON", id="on", n_clicks=0, color="success" , className="btn btn-primary me-2 mb-2"),
                            dbc.Button("OFF", id="off", n_clicks=0, color="danger", className="btn btn-primary me-2 mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),

                dbc.Row(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Up Mould Start", id="ums", n_clicks=0, className="btn btn-primary me-2 mb-2"),
                        dbc.Button("Up Mould End", id="ume", n_clicks=0, color="danger", className="btn btn-primary mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),


                dbc.Row(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Down Mould Start", id="dms", n_clicks=0, className="btn btn-primary me-2 mb-2"),
                        dbc.Button("Down Mould End", id="dme", n_clicks=0, color="danger", className="btn btn-primary mb-2"),
                        ],
                        className="gap-3"
                    ),
                    className="d-flex justify-content-center align-items-center mb-4",
                ),


                dbc.Row(
                    dbc.ButtonGroup(
                        [
                          dbc.Button("Adjustment/QC Approval Start", id="qas", n_clicks=0, className="btn btn-primary me-2 mb-2"),
                        dbc.Button("Adjustment/QC Approval End", id="qae", n_clicks=0, color="danger", className="btn btn-primary mb-2"),
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
                               dbc.Select(id="mould_list", options=mould_list)
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
    Output('dms', 'disabled'),
    Output('qas', 'disabled'),
    #stop buttons
    Output('off', 'disabled'),
    Output('ume', 'disabled'),
    Output('dme', 'disabled'),
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
    button_state_dms = True
    button_state_qas = True

    button_state_off = True  
    button_state_ume = True
    button_state_dme = True
    button_state_qae = True

    if status == "off":
        # no active mould on machine, only available option is up a new mould
        button_state_ums = False  
 
    elif status == "up mould in progress":
        # active mould but no other actions
        button_state_ume = False

    elif status == "active mould not running":
        button_state_on = False  
        button_state_dms = False
        button_state_qas = False

    elif status == "adjustment/qa in progress":
        button_state_qae = False

    elif status == "mass prod":
        button_state_off = False  

    
    elif status == "downmould in progess":
        button_state_dme = False


    return f"Status: {status}", f"Active Mould: {mould_id}", button_state_on, button_state_ums, button_state_dms, button_state_qas, button_state_off, button_state_ume, button_state_dme, button_state_qae


"""

UP MOULD

"""

@callback(
    Output("modal", "is_open"),
    [Input("ums", "n_clicks"), Input("close", "n_clicks"), Input("ok", "n_clicks")],
    [State("modal", "is_open"), State("machine_id", "value"), State("mould_list", "value")]
)
def up_mould(ums, close, ok,  is_open, machine_id, mould_id):
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
        try:
            # Database update
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = "UPDATE machine_list SET mould_id = %s, machine_status = 'up mould in progress' WHERE machine_code = %s"
                cursor.execute(sql, (str(mould_id), str(machine_id)))

                sql_insert = "INSERT INTO joblist (machine_code, mould_code, time_input) VALUES (%s, %s, NOW())"
                cursor.execute(sql_insert, (str(machine_id), str(mould_id)))


                connection.commit()
                #after inserting the query into the database, send a signal to esp
                #so now, when the mqtt receives the command "ums", will start a timer 
                #then when the esp receives a command "ume", insert a query into the database
                message = {"command": "ums"}
                
                mqttc.publish(mqtt_machine, payload=json.dumps(message))

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
def up_mould_end(ume, yes, no, is_open, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    # print(triggered_id)

    # When "ume" is clicked, open the modal
    if triggered_id == "ume":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-1":
        try:
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
                    # Create and publish the MQTT message
                    message = {
                        "command": "ume",
                        "main_id": str(main_id),
                        # "mould_id": str(mould_id) if mould_id else None,
                    }
                    mqttc.publish(mqtt_machine, payload=json.dumps(message))
                    # print(f"MQTT message published: {message}")
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

            message = {"command": "qas"}
            mqttc.publish(mqtt_machine, payload=json.dumps(message))

            return True  # Show the alert
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        connection.close()

    return dash.no_update

@callback(
    Output("confirmation-2", "is_open"),
    [Input("qae", "n_clicks"), Input("yes-2", "n_clicks"), Input("no-2", "n_clicks")],
    [State("confirmation-2", "is_open"), State("machine_id", "value")]
)
def adjustment_end(ume, yes, no, is_open, machine_id):
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    # When "ume" is clicked, open the modal
    if triggered_id == "qae":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-2":
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

                    message = {
                        "command": "qae",
                        "main_id": str(main_id),
                        # "mould_id": str(mould_id) if mould_id else None,
                    }
                    mqttc.publish(mqtt_machine, payload=json.dumps(message))


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

DOWN MOULD

"""



@callback(
    Output("alert-auto-dm", "is_open"),
    [Input("dms", "n_clicks")],
    [State("alert-auto-dm", "is_open"), State("machine_id", "value")]
)
def downmould_start(dms, alert, machine_id):
    # Check if the callback was triggered by the "qas" button
    mqtt_machine = f"machines/{machine_id}"
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    if triggered_id != "dms":
        # If not triggered by the button, do nothing (retain current state)
        return dash.no_update

    # Proceed with updating the database if "qas" was clicked
    try:
        connection = create_engine(db_connection_str).raw_connection()
        with connection.cursor() as cursor:
            sql = """
            UPDATE machine_list 
            SET machine_status = 'downmould in progess'
            WHERE machine_code = %s
            """
            cursor.execute(sql, (str(machine_id),))
            connection.commit()
            
            message = {"command": "dms"}
            mqttc.publish(mqtt_machine, payload=json.dumps(message))
            return True  # Show the alert
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        connection.close()

    return dash.no_update


@callback(
    Output("confirmation-3", "is_open"),
    [Input("dme", "n_clicks"), Input("yes-3", "n_clicks"), Input("no-3", "n_clicks")],
    [State("confirmation-3", "is_open"), State("machine_id", "value")]
)
def downmould_end(dme, yes, no, is_open, machine_id):
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    mqtt_machine = f"machines/{machine_id}"
    # When "ume" is clicked, open the modal
    if triggered_id == "dme":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-3":

        try:
            connection = create_engine(db_connection_str).raw_connection()
            with connection.cursor() as cursor:
                sql = """
                UPDATE machine_list 
                SET machine_status = 'off', mould_id = %s
                WHERE machine_code = %s
                """
                cursor.execute(sql, (None, str(machine_id),))
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

                    message = {
                        "command": "dme",
                        "main_id": str(main_id),
                    }
                    mqttc.publish(mqtt_machine, payload=json.dumps(message))
        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            connection.close()
        return False  # Close modal after action

    # When "no" is clicked, just close the modal without any action
    if triggered_id == "no-3":
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

            sql_insert = " INSERT INTO mass_production (machine_code) VALUES (%s)"
            cursor.execute(sql_insert, (str(machine_id),))
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
                mqttc.publish(mqtt_machine, payload=json.dumps(message))
            

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
                mqttc.publish(mqtt_machine, payload=json.dumps(message))
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


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
    # app.run_server(host="192.168.1.15",port=8050)
