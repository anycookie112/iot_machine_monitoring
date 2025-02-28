import dash_bootstrap_components as dbc
from dash import Input, Output, html, Dash, State, dash, dcc, callback_context, callback
from sqlalchemy import create_engine
import pandas as pd
import dash
from config.config import DB_CONFIG

db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
db_connection = create_engine(db_connection_str)



def fetch_data(): 
    df = pd.read_sql(f'''
        SELECT * FROM machine_list
    ''', con=db_connection)
    
    return df


df = fetch_data()

machines = []
for index, row in df.iterrows():
    machines.append(row)
# Example data for machines



# Function to create a box for each machine
dash.register_page(__name__, path='/page-1')

# Function to create a machine status card
def create_machine_box(machine):
    # Set card color based on machine status and ESP connection
    if machine["machine_status"] == "running" and machine["esp_status"] == "disconnected":
        card_color = "bg-danger text-white"
    elif machine["machine_status"] == "running" and machine["esp_status"] == "connected":
        card_color = "bg-success text-white"
    elif machine["machine_status"] != "running" and machine["esp_status"] == "connected":
        card_color = "bg-primary text-white"
    else:
        card_color = "bg-secondary text-white"

    return dbc.Card(
        dbc.CardBody([
            html.H4(f"Machine {machine['machine_code']}", className="card-title"),
            html.P(id=f"status-{machine['machine_code']}", children=f"Status: {machine['machine_status']}", className="card-text"),
            html.P(id=f"Mould-{machine['machine_code']}", children=f"Active Mould: {machine['mould_id']}", className="card-text"),
            html.P(id=f"esp_status-{machine['machine_code']}", children=f"Esp Status: {machine['esp_status']}", className="card-text"),
        ]),
        className=f"m-2 {card_color}",
        style={"width": "18rem", "display": "inline-block"},
    )

# Layout
layout = html.Div([
    html.H1("IoT Machine Status Dashboard", className="text-center mb-4"),
    
    # Interval component for automatic refresh every 5 seconds
    dcc.Interval(id="interval-component", interval=5000, n_intervals=0),

    html.Div(id="machine-cards", className="d-flex flex-wrap justify-content-center")
])

# Callback to update machine cards every 5 seconds
@callback(
    Output("machine-cards", "children"),
    Input("interval-component", "n_intervals")
)
def update_cards(n):
    # Fetch updated machine status (replace with real data fetching)
    updated_machines = []
    
    df_updated = fetch_data()
    updated_machines = []
    for index, row in df_updated.iterrows():
        updated_machines.append(row)
    return [create_machine_box(machine) for machine in updated_machines]




