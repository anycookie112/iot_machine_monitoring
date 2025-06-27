# pages/logout.py

import dash
from dash import html, dcc, callback, Output, Input
from flask_login import logout_user
from flask import session

dash.register_page(__name__, path="/logout")

layout = html.Div([dcc.Location(id='url-logout')])

@callback(
    Output('url-logout', 'pathname'),
    Input('url-logout', 'pathname'),
    prevent_initial_call=True
)
def perform_logout(_):
    # Clear session and log out
    session.clear()
    logout_user()

    # Redirect back to login
    return "/login"
