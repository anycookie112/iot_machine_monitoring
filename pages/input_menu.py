import dash_bootstrap_components as dbc
from dash import Input, Output, html, State, dash, dcc, callback_context, callback
from sqlalchemy import text
import pandas as pd
import json
import dash

from utils.db import get_db_engine, get_raw_connection
from utils.filter_mould import get_customer_list, get_mould_list
from utils.mqtt import publish_message


def _get_machine_status(cursor, machine_id):
    cursor.execute(
        """
        SELECT machine_status
        FROM machine_list
        WHERE machine_code = %s
        """,
        (str(machine_id),),
    )
    result = cursor.fetchone()
    return result[0] if result else None


def _get_latest_main_id(cursor, machine_id):
    cursor.execute(
        """
        SELECT main_id
        FROM joblist
        WHERE machine_code = %s
        ORDER BY main_id DESC
        LIMIT 1
        """,
        (str(machine_id),),
    )
    result = cursor.fetchone()
    return result[0] if result else None


def _get_active_mass_production(cursor, machine_id):
    cursor.execute(
        """
        SELECT mp_id, main_id, mould_id
        FROM mass_production
        WHERE machine_code = %s
          AND COALESCE(status, '') <> 'completed'
        ORDER BY mp_id DESC
        LIMIT 1
        """,
        (str(machine_id),),
    )
    result = cursor.fetchone()
    return result if result else (None, None, None)


def _get_latest_action_start(cursor, main_id, action):
    cursor.execute(
        """
        SELECT time_input
        FROM monitoring
        WHERE main_id = %s
          AND action = %s
        ORDER BY time_input DESC, idmonitoring DESC
        LIMIT 1
        """,
        (str(main_id), action),
    )
    result = cursor.fetchone()
    return result[0] if result else None


def _get_elapsed_seconds(cursor, main_id, action):
    start_time = _get_latest_action_start(cursor, main_id, action)
    if not start_time:
        return 0

    cursor.execute(
        "SELECT GREATEST(TIMESTAMPDIFF(SECOND, %s, NOW()), 0)",
        (start_time,),
    )
    result = cursor.fetchone()
    return int(result[0]) if result and result[0] is not None else 0

def _fetch_machine_row(machine_id):
    query = text(
        """
        SELECT machine_code, mould_id, machine_status
        FROM machine_list
        WHERE machine_code = :machine_code
        """
    )
    df = pd.read_sql(query, con=get_db_engine(), params={"machine_code": machine_id})
    return df.iloc[0] if not df.empty else None


def _build_mould_options(customer=None):
    return [
        {"label": mould_code, "value": mould_code}
        for mould_code in get_mould_list(customer)
    ]


def _build_customer_options():
    return [
        {"label": customer, "value": customer}
        for customer in get_customer_list()
    ]


dash.register_page(__name__, path="/")

inline_checklist = html.Div(
    [
        dbc.Label("Customer"),
        dbc.RadioItems(
            options=[],
            value=None,
            id="checklist-inline-input",
            inline=True,
        ),
    ]
)

# All items in this list will have the value the same as the label
select = html.Div(
    dbc.Select(
        options=[],
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

correct_customer_checklist = html.Div(
    [
        dbc.Label("Customer"),
        dbc.RadioItems(
            options=[],
            value=None,
            id="correct-customer-input",
            inline=True,
        ),
    ]
)

correct_mould_select = html.Div(
    dbc.Select(
        options=[],
        id="correct-mould-select",
    ),
    className="py-2",
)


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
    dbc.Alert(
            "Mould updated while production continues",
            id="alert-auto-correct",
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
                            dbc.Button("CORRECT MOULD", id="correct-mould", n_clicks=0, color="warning", className="btn btn-primary me-2 mb-2"),
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
                               "Confirm complete change mould?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-1",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-1", className="ms-auto", n_clicks=0),
                    dbc.Input(id="name-2", placeholder="Name Mould Setter", type="text"),
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
                               "Confirm complete adjustment?"
                        ]),
                dbc.ModalFooter([
                    dbc.Button("Yes", id="yes-2",  n_clicks=0),
                    dbc.Button("No", color="primary", id="no-2", className="ms-auto", n_clicks=0),
                    dbc.Input(id="name", placeholder="Name Adjustment Setter", type="text"),
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
    html.Div([
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Correct Active Mould")),
                dbc.ModalBody([
                    html.P("Update the mould for the current production run without stopping the machine."),
                    correct_customer_checklist,
                    correct_mould_select,
                ]),
                dbc.ModalFooter([
                    dbc.Button("Close", id="close-correct", n_clicks=0),
                    dbc.Button("Apply", color="primary", id="apply-correct", className="ms-auto", n_clicks=0),
                ]),
            ],
            id="correct-mould-modal",
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
    Output('correct-mould', 'disabled'),
    Output('ume', 'disabled'),
    # Output('dme', 'disabled'),
    Output('qae', 'disabled'),
    ],
    [
    Input("machine_id", "value"), Input("refresh", 'n_intervals')
    ]
)

def update_output(value, n):
    try:
        machine_row = _fetch_machine_row(value)
    except Exception as exc:
        return (
            f"Status: Database unavailable ({exc})",
            "Active Mould: Unknown",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        )

    if machine_row is None:
        return (
            "Status: Unknown machine",
            "Active Mould: Unknown",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        )

    mould_id = machine_row["mould_id"]
    status = machine_row["machine_status"]
    # Disabled by default
    button_state_on = True  
    button_state_ums = True 
    # button_state_dms = True
    button_state_qas = True

    button_state_off = True  
    button_state_correct = True
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
        button_state_correct = False

    elif status == "adjustment/qa in progress":
        button_state_qae = False

    elif status == "mass prod":
        button_state_off = False  
        button_state_correct = False

    return f"Status: {status}", f"Active Mould: {mould_id}", button_state_on, button_state_ums, button_state_qas, button_state_off, button_state_correct, button_state_ume, button_state_qae


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
    connection = None

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
            # toggle_machine_timer(machine_id)
            # Database update
            connection = get_raw_connection()
            with connection.cursor() as cursor:
                current_status = _get_machine_status(cursor, machine_id)
                if current_status == "change mould in progress":
                    return False

                sql = "UPDATE machine_list SET mould_id = %s, machine_status = 'change mould in progress' WHERE machine_code = %s"
                cursor.execute(sql, (str(mould_id), str(machine_id)))

                sql_insert = "INSERT INTO joblist (machine_code, mould_code, time_input) VALUES (%s, %s, NOW())"
                cursor.execute(sql_insert, (str(machine_id), str(mould_id)))
                main_id = cursor.lastrowid


                sql_insert_log = """
                INSERT INTO monitoring (main_id, action, time_taken, time_input)
                VALUES (%s, "change mould start", %s, NOW())
                """
                cursor.execute(sql_insert_log, (str(main_id), 0,))

                connection.commit()

                message = json.dumps({"command": "ums"})
                publish_message(mqtt_machine, message, qos=2)

        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            if connection:
                connection.close()
        return False  # Close the modal after successful action

    # Default case: No button was clicked
    return is_open

@callback(
    Output("confirmation-1", "is_open"),
    [Input("ume", "n_clicks"),
     Input("yes-1", "n_clicks"),
     Input("no-1", "n_clicks"),
     Input("name-2", "value")],
    [State("confirmation-1", "is_open"),
     State("machine_id", "value")]
)
def change_mould_end(ume, yes, no, name, is_open, machine_id):
    triggered = callback_context.triggered
    connection = None

    # Handle first page load (no triggers)
    if not triggered or triggered[0]["prop_id"] == ".":
        return is_open if is_open is not None else False

    triggered_id = triggered[0]["prop_id"].split(".")[0]
    mqtt_machine = f"machines/{machine_id}" if machine_id else None

    # Open modal when UME button clicked
    if triggered_id == "ume":
        return True

    if triggered_id == "no-1":
        return False

    # Keep modal open if name is missing
    if not name or not name.strip():
        return True

    # Yes button: update DB and close modal
    if triggered_id == "yes-1":
        try:
            connection = get_raw_connection()
            with connection.cursor() as cursor:
                current_status = _get_machine_status(cursor, machine_id)
                if current_status != "change mould in progress":
                    return False

                main_id = _get_latest_main_id(cursor, machine_id)
                if main_id is None:
                    return False

                elapsed_seconds = _get_elapsed_seconds(cursor, main_id, "change mould start")

                # Update machine status
                sql_update = """
                UPDATE machine_list 
                SET machine_status = 'active mould not running'
                WHERE machine_code = %s
                """
                cursor.execute(sql_update, (machine_id,))

                sql_insert = """
                INSERT INTO monitoring (main_id, action, time_taken, time_input, remarks)
                VALUES (%s, "change mould end", %s, NOW(), %s)
                """
                cursor.execute(sql_insert, (str(main_id), elapsed_seconds, name))
                connection.commit()

                if mqtt_machine:
                    message = json.dumps({"command": "ume"})
                    publish_message(mqtt_machine, message, qos=2)

            connection.commit()
        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            if connection:
                connection.close()
        return False

    # Otherwise, keep current state
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
    print("adjustment() called")
    
    connection = None  # Ensure connection is always defined

    try:
        triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        print("Triggered by:", triggered_id)
        
        if "qas" not in triggered_id:
            return dash.no_update

        connection = get_raw_connection()
        with connection.cursor() as cursor:
            print("Connected to DB")

            current_status = _get_machine_status(cursor, machine_id)
            if current_status == "adjustment/qa in progress":
                return True
            if current_status != "active mould not running":
                return dash.no_update

            # Update machine_list
            sql = """
            UPDATE machine_list 
            SET machine_status = 'adjustment/qa in progress'
            WHERE machine_code = %s
            """
            cursor.execute(sql, (str(machine_id),))
            connection.commit()

            main_id = _get_latest_main_id(cursor, machine_id)
            print("Fetched main_id:", main_id)

            if not main_id:
                print(f"No joblist entry found for machine_id={machine_id}")
                return dash.no_update

            sql_insert = """
            INSERT INTO monitoring (main_id, action, time_taken, time_input)
            VALUES (%s, 'adjustment start', %s, NOW())
            """
            cursor.execute(sql_insert, (str(main_id), 0))
            connection.commit()
            print("Insert success")

            message = json.dumps({"command": "qas"})
            publish_message(f"machines/{machine_id}", message, qos=2)

            return True

    except Exception as e:
        import traceback
        print("DB Error:", e)
        traceback.print_exc()

    finally:
        if connection:  # Only close if it was assigned
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
    connection = None

    # When "ume" is clicked, open the modal
    if triggered_id == "qae":
        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-2":
        if not name or not name.strip():
            # If name is empty or just whitespace, do nothing (keep modal open)
            return True
        
        try:
            connection = get_raw_connection()
            with connection.cursor() as cursor:
                current_status = _get_machine_status(cursor, machine_id)
                if current_status != "adjustment/qa in progress":
                    return False

                main_id = _get_latest_main_id(cursor, machine_id)
                if main_id is None:
                    return False

                elapsed_seconds = _get_elapsed_seconds(cursor, main_id, "adjustment start")

                sql = """
                UPDATE machine_list 
                SET machine_status = 'active mould not running'
                WHERE machine_code = %s
                """
                cursor.execute(sql, (str(machine_id),))
                connection.commit()

                sql_insert = """
                INSERT INTO monitoring (main_id, action, time_taken, time_input, remarks)
                VALUES (%s, "adjustment end", %s, NOW(), %s)
                """
                cursor.execute(sql_insert, (str(main_id), elapsed_seconds, name,))
                connection.commit()

                message = json.dumps({"command": "qae"})
                publish_message(mqtt_machine, message, qos=2)



        except Exception as e:
            print(f"Error updating database: {e}")
        finally:
            if connection:
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
    connection = None
    # Check if the callback was triggered by the "qas" button
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    if triggered_id != "on":
        # If not triggered by the button, do nothing (retain current state)
        return dash.no_update

    # Proceed with updating the database if "qas" was clicked
    try:
        connection = get_raw_connection()
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
                sql_insert = " INSERT INTO mass_production (machine_code, mould_id, main_id) VALUES (%s, %s, %s)"
                cursor.execute(sql_insert, (str(machine_id), str(mould_id), str(main_id)))
                last_inserted_id = cursor.lastrowid
                
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
        if connection:
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
    connection = None
    # When "ume" is clicked, open the modal
    if triggered_id == "off":

        return True  # Open modal

    # When "yes" is clicked, update the database and close the modal
    if triggered_id == "yes-4":
        try:
            connection = get_raw_connection()
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
            if connection:
                connection.close()
        return False  # Close modal after action

    # When "no" is clicked, just close the modal without any action
    if triggered_id == "no-4":
        return False  # Close modal

    # Default: Return current modal state if no input is triggered
    return is_open


@callback(
    Output("correct-customer-input", "options"),
    Input("machine_id", "value")
)
def refresh_correct_customer_options(_machine_id):
    try:
        return _build_customer_options()
    except Exception:
        return []


@callback(
    Output("correct-mould-select", "options"),
    Input("correct-customer-input", "value")
)
def correct_mould_filter(customer):
    try:
        return _build_mould_options(customer)
    except Exception:
        return []


@callback(
    Output("correct-mould-modal", "is_open"),
    Output("alert-auto-correct", "is_open"),
    Output("refresh", "n_intervals"),
    Input("correct-mould", "n_clicks"),
    Input("close-correct", "n_clicks"),
    Input("apply-correct", "n_clicks"),
    State("correct-mould-modal", "is_open"),
    State("machine_id", "value"),
    State("correct-mould-select", "value"),
    State("refresh", "n_intervals"),
    prevent_initial_call=True,
)
def correct_active_mould(open_clicks, close_clicks, apply_clicks, is_open, machine_id, mould_id, refresh_count):
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else None

    if triggered_id == "correct-mould":
        return True, False, refresh_count

    if triggered_id == "close-correct":
        return False, False, refresh_count

    if triggered_id != "apply-correct":
        return is_open, False, refresh_count

    if not mould_id or not str(mould_id).strip():
        return True, False, refresh_count

    connection = None

    try:
        connection = get_raw_connection()
        with connection.cursor() as cursor:
            current_status = _get_machine_status(cursor, machine_id)
            if current_status not in {"mass prod", "active mould not running"}:
                return False, False, refresh_count

            mp_id, active_main_id, _current_mould = _get_active_mass_production(cursor, machine_id)
            main_id = active_main_id if active_main_id is not None else _get_latest_main_id(cursor, machine_id)

            cursor.execute(
                """
                UPDATE machine_list
                SET mould_id = %s
                WHERE machine_code = %s
                """,
                (str(mould_id), str(machine_id)),
            )

            if mp_id is not None:
                cursor.execute(
                    """
                    UPDATE mass_production
                    SET mould_id = %s
                    WHERE mp_id = %s
                    """,
                    (str(mould_id), str(mp_id)),
                )

            if main_id is not None:
                cursor.execute(
                    """
                    UPDATE joblist
                    SET mould_code = %s
                    WHERE main_id = %s
                    """,
                    (str(mould_id), str(main_id)),
                )

            connection.commit()
    except Exception as e:
        print(f"Error correcting mould during production: {e}")
        return True, False, refresh_count
    finally:
        if connection:
            connection.close()

    next_refresh = 0 if refresh_count is None or refresh_count < 0 else refresh_count + 1
    return False, True, next_refresh


@callback(
    Output('shorthand-select', 'options'),
    Input('checklist-inline-input', 'value')
)

def mould_filter(customer):
    try:
        return _build_mould_options(customer)
    except Exception:
        return []


@callback(
    Output('checklist-inline-input', 'options'),
    Input('machine_id', 'value')
)
def refresh_customer_options(_machine_id):
    try:
        return _build_customer_options()
    except Exception:
        return []
    
