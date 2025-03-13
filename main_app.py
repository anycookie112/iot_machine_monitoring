import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
from utils.mqtt import get_mqtt_client

mqttc = get_mqtt_client()
app = dash.Dash(__name__,use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

# Sidebar layout
sidebar = html.Div(
    [
        html.H2("Menu", className="display-4"),
        html.Hr(),
        html.P("Navigation", className="lead"),
        dbc.Nav(
            [
                dbc.NavLink("Home", href="/", active="exact"), 
                dbc.NavLink("Machine Status", href="/page-1", active="exact"),
                dbc.NavLink("Mould Service Status", href="/page-2", active="exact"),
                dbc.NavLink("Machine Output", href="/page-3", active="exact"),
            ],
            vertical=True,
            pills=True,
        ), 
    ],
    style={ 
        "position": "fixed",
        "top": 0,
        "left": 0,    
        "bottom": 0, 
        "width": "16rem",
        "padding": "2rem 1rem",
        "background-color": "#f8f9fa",
    },
)

# Main content layout
content = html.Div(dash.page_container, style={"margin-left": "18rem", "padding": "2rem"})

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

if __name__ == "__main__":
    # app.run_server(port=8888, debug=True) 
    app.run_server(port=8888)