import dash_bootstrap_components as dbc
from dash import Input, Output, html, Dash
from config.config import MQTT_CONFIG, DB_CONFIG
from sqlalchemy import create_engine
import pandas as pd
import numpy as np

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"


def removeduplicate(data):
    countdict = {}
    for element in data:
        if element in countdict.keys():
            countdict[element] += 1
        else:
            countdict[element] = 1
    data.clear()
    for key in countdict.keys():
        data.append(key)

def get_mould_list(customer = None):
    if customer:
        query = f"""
            SELECT * from mould_list
            WHERE customer = "{customer}"
        """
    else:
        query = f"""
            SELECT * from mould_list
        """
    
    df = pd.read_sql(query, con=db_connection_str)
    mould_code = df["mould_code"].to_list()
    removeduplicate(mould_code)
    # print(mould_code)
    return mould_code

mould_code = get_mould_list()


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
        mould_code,
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

app.layout = html.Div(
    [
        inline_checklist,
        short_hand
     ])


