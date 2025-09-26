
from datetime import datetime, timedelta
from sqlalchemy import create_engine,text
import plotly.graph_objects as go
import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config import DB_CONFIG


import dash
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from sqlalchemy import create_engine, text



from dash import html, dcc, Input, Output, callback, callback_context



engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

# df = pd.read_sql(f'''
#     SELECT * FROM machine_list
# ''', con=db_connection_str)

# print(df)
# with db_connection_str.begin() as conn:
#     conn.execute(
#         text("""
#             INSERT INTO mould_list (mould_code, model_number, part_name, part_code, standard_ct)
#             VALUES (:mould_code, :model_number, :part_name, :part_code, :standard_ct)
#         """),
#         {
#             "mould_code": 123,
#             "model_number": "model_123",
#             "part_name": "Part A",
#             "part_code": "P123",
#             "standard_ct": 30
#         }
#     )

# app = Dash(__name__)
dash.register_page(__name__, path="/mould")

# Example: list of customers (you can fetch dynamically from DB instead)
CUSTOMERS = [
                {"label": "Panasonic", "value": 'panasonic'},
                {"label": "HEM", "value": 'hem'},
                {"label": "Hfuji", "value": 'hfuji'},
                {"label": "Yamada", "value": 'yamada'},
                {"label": "Osaka", "value": 'osaka'},
                {"label": "SMK", "value": 'smk'},
                {"label": "UD", "value": 'ud'},
]
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Add New Mould", className="text-center text-primary mb-4"))
        ),

        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Mould Code"),
                                dbc.Input(id="mould_code", placeholder="Enter mould code")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Model Number"),
                                dbc.Input(id="model_number", placeholder="Enter model number")
                            ], md=6),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Part Name"),
                                dbc.Input(id="part_name", placeholder="Enter part name")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Part Code"),
                                dbc.Input(id="part_code", placeholder="Enter part code")
                            ], md=6),
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Standard CT"),
                                dbc.Input(id="standard_ct", type="number", placeholder="Enter standard cycle time")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Customer"),
                                dcc.Dropdown(
                                    id="customer_dropdown",
                                    options=CUSTOMERS,
                                    placeholder="Select customer",
                                    clearable=False
                                )
                            ], md=6),
                        ], className="mb-3"),

                        dbc.Button("Submit", id="submit_btn", color="primary", className="w-100"),
                        html.Div(id="status_msg", className="mt-3 fw-bold")
                    ])
                ),
                md=8, className="offset-md-2"
            )
        )
    ],
    fluid=True
)

# Callback to insert + clear inputs
@callback(
    Output("status_msg", "children"),
    Output("mould_code", "value"),
    Output("model_number", "value"),
    Output("part_name", "value"),
    Output("part_code", "value"),
    Output("standard_ct", "value"),
    Output("customer_dropdown", "value"),
    Input("submit_btn", "n_clicks"),
    State("mould_code", "value"),
    State("model_number", "value"),
    State("part_name", "value"),
    State("part_code", "value"),
    State("standard_ct", "value"),
    State("customer_dropdown", "value"),
    prevent_initial_call=True
)
def insert_mould(n_clicks, mould_code, model_number, part_name, part_code, standard_ct, customer_id):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO mould_list (mould_code, model_number, part_name, part_code, standard_ct, customer_id)
                    VALUES (:mould_code, :model_number, :part_name, :part_code, :standard_ct, :customer_id)
                """),
                {
                    "mould_code": mould_code,
                    "model_number": model_number,
                    "part_name": part_name,
                    "part_code": part_code,
                    "standard_ct": standard_ct,
                    "customer_id": customer_id
                }
            )
        return (
            dbc.Alert(f"Mould {mould_code} inserted successfully!", color="success"),
            None, None, None, None, None, None
        )
    except Exception as e:
        return (dbc.Alert(f"Error: {e}", color="danger"),
                mould_code, model_number, part_name, part_code, standard_ct, customer_id)

# if __name__ == "__main__":
#     app.run_server(debug=True)