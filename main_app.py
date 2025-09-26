import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
from utils.mqtt import get_mqtt_client
from dash import html, dcc, Input, Output, State, callback

mqttc = get_mqtt_client()
app = dash.Dash(__name__,use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
SIDEBAR_WIDTH = "16rem"
SIDEBAR_COLLAPSED_WIDTH = "0"

# Sidebar content (without toggle button)
sidebar_content = html.Div([
    html.H2("Menu", className="display-4"),
    html.Hr(),
    html.P("Navigation", className="lead"),
    dbc.Nav(
        [
            dbc.NavLink("Home", href="/", active="exact"),
            dbc.NavLink("Machine Status", href="/page-1", active="exact"),
            dbc.NavLink("Daily Report", href="/daily", active="exact"),
            dbc.NavLink("Add Mould", href="/mould", active="exact"),
            dbc.NavLink("Live", href="/live", active="exact"),
        ],
        vertical=True,
        pills=True,
    ),
])

# Sidebar container
sidebar = html.Div(
    [
        dbc.Collapse(sidebar_content, id="sidebar-collapse", is_open=True),
    ],
    id="sidebar",
    style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": SIDEBAR_WIDTH,
        "padding": "2rem 1rem",
        "background-color": "#f8f9fa",
        "transition": "width 0.3s ease",
        "overflow-x": "hidden",
        "zIndex": 1000,
    },
)

# Toggle button floating on top left
toggle_button = html.Div(
    dbc.Button("☰", id="sidebar-toggle", color="primary", n_clicks=0, size="sm"),
    style={
        "position": "fixed",
        "top": "10px",
        "left": "10px",
        "zIndex": 1100,  # above the sidebar
    },
)

# Main content
content = html.Div(
    dash.page_container,
    id="main-content",
    style={
        "margin-left": SIDEBAR_WIDTH,
        "padding": "2rem",
        "transition": "margin-left 0.3s ease",
    },
)

# App layout
app.layout = html.Div([toggle_button, sidebar, content])

# Callback to toggle sidebar and shift content
@app.callback(
    Output("sidebar-collapse", "is_open"),
    Output("sidebar", "style"),
    Output("main-content", "style"),
    Input("sidebar-toggle", "n_clicks"),
    State("sidebar-collapse", "is_open"),
)
def toggle_sidebar(n_clicks, is_open):
    if n_clicks:
        new_is_open = not is_open
    else:
        new_is_open = is_open

    # Sidebar style update
    sidebar_style = {
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": SIDEBAR_WIDTH if new_is_open else SIDEBAR_COLLAPSED_WIDTH,
        "padding": "2rem 1rem" if new_is_open else "0",
        "background-color": "#f8f9fa",
        "transition": "width 0.3s ease",
        "overflow-x": "hidden",
        "zIndex": 1000,
    }

    # Content shifts depending on sidebar
    content_style = {
        "margin-left": SIDEBAR_WIDTH if new_is_open else SIDEBAR_COLLAPSED_WIDTH,
        "padding": "2rem",
        "transition": "margin-left 0.3s ease",
    }

    return new_is_open, sidebar_style, content_style

if __name__ == "__main__":
    app.run_server(port=8888, debug=True) 
    # app.run_server(port=8888)