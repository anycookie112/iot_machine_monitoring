import dash_ag_grid as dag
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.sql import text  # Import text function
dash.register_page(__name__, path='/page-2')

# Database connection function
def fetch_data():
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    db_connection = create_engine(db_connection_str)

    df = pd.read_sql("SELECT * FROM mould_masterlist", con=db_connection)
    filtered_df = df[df["service_status"] == 1]
    data_excluded = filtered_df.drop(columns=['service_status', 'service_increment'], errors='ignore')
    
    return data_excluded

# Initial Data Fetch
data_excluded = fetch_data()

# Column definitions
columndef = [{"field": "mould_code", "checkboxSelection": True, "headerCheckboxSelection": True}] + \
            [{"field": i} for i in data_excluded.columns]

# AgGrid Table
grid = dag.AgGrid(
    id="service-table",
    rowData=data_excluded.to_dict("records"),
    dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
    columnDefs=columndef,
    columnSize="sizeToFit",
)

# Input Section
input_section = dbc.Card([
    dbc.CardHeader("Service Details"),
    dbc.CardBody([
        dcc.Store(id="selected-mould", data=None),  # Store selected mould
        html.P("Selected Mould Code:"),
        html.H5(id="selected-mould-code", children="None", className="text-primary"),  # Display selected mould

        dbc.Label("Service Type"),
        dcc.Dropdown(
            id="service-type",
            options=[
                {"label": "Minor Service", "value": 1},
                {"label": "Major Service", "value": 2}
            ],
            value=1,
            clearable=False
        ),

        dbc.Label("Remarks"),
        dbc.Input(id="service-remarks", placeholder="Enter remarks...", type="text"),

        dbc.Button("Submit Service Record", id="submit-service", color="success", className="mt-3"),
        html.Div(id="submission-status", className="mt-2")  # Status message
    ])
], className="mt-4")

# Layout
layout = html.Div([
    html.H1("Mould Service Table:", className="card-title"),
    
    # Refresh Button
    dbc.Button("Refresh Table", id="refresh-btn", color="primary", className="mt-3 mb-3"),
    dcc.Interval(id="refresh-table", n_intervals=-1),
    grid,
    input_section  # Data input section below the table
])

# Callback to update selected mould info
@dash.callback(
    Output("selected-mould", "data"),
    Output("selected-mould-code", "children"),
    Input("service-table", "selectedRows")
)
def update_selected_mould(selected_rows):
    if selected_rows:
        mould_code = selected_rows[0]["mould_code"]
        return mould_code, f"Selected: {mould_code}"
    return None, "None"

# Callback to handle submission
@dash.callback(
    Output("submission-status", "children"),
    Input("submit-service", "n_clicks"),
    State("selected-mould", "data"),
    State("service-type", "value"),
    State("service-remarks", "value"),
    prevent_initial_call=True  # Prevent execution on page load
)
def submit_service_record(n_clicks, mould_code, service_type, remarks):
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    
    if not n_clicks:
        return ""
    
    if not mould_code:
        return dbc.Alert("No mould selected!", color="danger")

    # Ensure service_type is an integer
    try:
        service_type = int(service_type)
    except ValueError:
        return dbc.Alert("Invalid service type!", color="danger")

    # Convert service type to string if necessary
    service_type_str = "minor" if service_type == 1 else "major"

    print(f"Submitting Service: Mould: {mould_code}, Type: {service_type_str}, Remarks: {remarks}")

    # Connect to the database using SQLAlchemy
    engine = create_engine(db_connection_str)
    connection = engine.connect()

    try:
        with connection.begin():  # Use transaction handling
            if service_type == 1:
                sql_insert = text("""
                    INSERT INTO service_history (mould_code, service_type, remarks) 
                    VALUES (:mould_code, :service_type, :remarks)
                """)
                print("Executing INSERT:", sql_insert)
                connection.execute(sql_insert, {
                    "mould_code": mould_code,
                    "service_type": service_type_str,
                    "remarks": remarks
                })

            elif service_type == 2:
                sql_update = text("""
                    UPDATE mould_masterlist
                    SET next_service_shot_count = total_shot_count + service_increment, 
                        service_status = 0
                    WHERE mould_code = :mould_code
                """)
                print("Executing UPDATE:", sql_update)
                connection.execute(sql_update, {"mould_code": mould_code})

        return dbc.Alert("Service record submitted successfully!", color="success")

    except Exception as e:
        print("Database error:", e)
        return dbc.Alert(f"Database error: {e}", color="danger")

    finally:
        connection.close()

# Callback to refresh table data
@dash.callback(
    Output("service-table", "rowData"),
    Input("refresh-btn", "n_clicks"),
    Input("refresh-table", 'n_intervals'),

    prevent_initial_call=True  # Prevent callback from firing on page load
)
def refresh_table(n_clicks, submit):
    updated_data = fetch_data()  # Fetch updated data from DB
    return updated_data.to_dict("records")



"""
can add a input button to go add amould to the list for service/problems
means like, if mould A has a problem (pin problem), let the user pick the mould and 
put it up for service, like a ticket program, when there is mould problem send a ticket 
the ticket will stay there till finish service
maybe add another table
mould problem database


"""