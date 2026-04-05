import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, callback, dcc, html
from sqlalchemy import create_engine

from config.config import DB_CONFIG


db_connection_str = (
    f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
)
db_connection = create_engine(db_connection_str)

dash.register_page(__name__, path="/page-1")


def fetch_data():
    return pd.read_sql("SELECT * FROM machine_list", con=db_connection)


def machine_card_class(machine_status, esp_status):
    status = (machine_status or "").strip().lower()
    esp = (esp_status or "").strip().lower()

    if esp == "disconnected":
        return "bg-danger text-white"
    if status == "mass prod":
        return "bg-success text-white"
    if status in {"change mould in progress", "adjustment/qa in progress"}:
        return "bg-warning text-dark"
    if status == "active mould not running":
        return "bg-primary text-white"
    return "bg-secondary text-white"


def create_machine_box(machine):
    return dbc.Card(
        dbc.CardBody(
            [
                html.H4(f"Machine {machine['machine_code']}", className="card-title"),
                html.P(
                    id=f"status-{machine['machine_code']}",
                    children=f"Status: {machine['machine_status']}",
                    className="card-text",
                ),
                html.P(
                    id=f"mould-{machine['machine_code']}",
                    children=f"Active Mould: {machine['mould_id']}",
                    className="card-text",
                ),
                html.P(
                    id=f"esp_status-{machine['machine_code']}",
                    children=f"ESP Status: {machine['esp_status']}",
                    className="card-text",
                ),
            ]
        ),
        className=f"m-2 {machine_card_class(machine['machine_status'], machine['esp_status'])}",
        style={"width": "18rem", "display": "inline-block"},
    )


layout = html.Div(
    [
        html.H1("IoT Machine Status Dashboard", className="text-center mb-4"),
        dcc.Interval(id="interval-component", interval=5000, n_intervals=0),
        html.Div(id="machine-cards", className="d-flex flex-wrap justify-content-center"),
    ]
)


@callback(
    Output("machine-cards", "children"),
    Input("interval-component", "n_intervals"),
)
def update_cards(_n):
    df_updated = fetch_data()
    return [create_machine_box(machine) for _, machine in df_updated.iterrows()]
