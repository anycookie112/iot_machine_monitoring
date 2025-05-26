import time
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



class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""

class Timer:
    def __init__(self):
        self._start_time = None

    def start(self):
        """Start a new timer"""
        if self._start_time is not None:
            raise TimerError(f"Timer is running. Use .stop() to stop it")

        self._start_time = time.perf_counter()

    def stop(self):
        """Stop the timer, and report the elapsed time"""
        if self._start_time is None:
            raise TimerError(f"Timer is not running. Use .start() to start it")

        elapsed_time = time.perf_counter() - self._start_time
        self._start_time = None
        return elapsed_time
        # print(f"Elapsed time: {elapsed_time:0.4f} seconds")




t = Timer()



import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout with two buttons and a text display
app.layout = html.Div(
    [
        html.H1("Button Click Example", style={"textAlign": "center", "marginBottom": "20px"}),

        # Buttons
        html.Div(
            [
                html.Button("Button 1", id="button-1", n_clicks=0, style={"marginRight": "10px"}),
                html.Button("Button 2", id="button-2", n_clicks=0),
            ],
            style={"textAlign": "center", "marginBottom": "20px"}
        ),

        # Text display
        html.Div(id="output-text", style={"textAlign": "center", "fontSize": "20px", "marginTop": "20px"}),
        html.Div(id="output-text2", style={"textAlign": "center", "fontSize": "20px", "marginTop": "20px"}),

    ],
    style={"padding": "20px", "fontFamily": "Arial, sans-serif"}
)


# Callback to update the text display based on Button 1 clicks
@app.callback(
    Output("output-text", "children"),
    [Input("button-1", "n_clicks")],
    prevent_initial_call=True  # Prevent the callback from running on app load
)
def update_output(n_clicks_1):
    t.start()
    print("Button 1 clicked")
    return "Hi"

# Callback to update the text display based on Button 2 clicks
@app.callback(
    Output("output-text2", "children"),
    [Input("button-2", "n_clicks")],
    prevent_initial_call=True  # Prevent the callback from running on app load
)
def update_output(n_clicks_2):
    end = t.stop()
    print("end time")
    return end




# Run the app
if __name__ == "__main__":
    app.run_server(port=8888, debug=True)