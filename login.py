from flask import Flask, request, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import dash
from dash import html, dcc, Input, Output, State, no_update
import pandas as pd
from datetime import datetime, timezone, timedelta
import dash_bootstrap_components as dbc
import os
import sys
# print("Python Path:", sys.path)
# print("Current Working Directory:", os.getcwd())
# dash.register_page(__name__, path="/login", name="Login Page")

server = Flask(__name__)
app = dash.Dash(__name__, server=server,
                title='Example Dash login',
                update_title='Loading...',
                use_pages=True, 
                pages_folder=os.path.join(os.getcwd(), "pages"),  # Only look in the current working directory
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True)


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Location(id='redirect', refresh=True),
    dcc.Store(id='login-status', storage_type='session'),

    html.H1('Secondary Rejection %'),

    # Create Navbar with dynamic page links
    html.Div([
        
        dbc.NavbarSimple(
            children=[
                # Dynamically generate links from dash.page_registry
                dbc.NavItem(
                    dcc.Link(
                        page['name'],  # Page name
                        href=page["relative_path"],  # Page URL
                        className="nav-link text-light",  # Apply Bootstrap styling
                    )
                ) for page in dash.page_registry.values()
            ],
            brand="My App",  # Navbar brand
            brand_href="/",  # Link to home page
            color="primary",  # Navbar color
            dark=True  # Dark mode styling for the navbar
        ),
    ]),

    # Page content goes here (dash.page_container)
    dash.page_container
])

# Updating the Flask Server configuration with Secret Key to encrypt the user session cookie
server.config.update(SECRET_KEY=os.getenv('SECRET_KEY'))
# server.config.config['PERMANENT_SESSION_LIFETIME'] =  timedelta(minutes=5)

# Login manager object will be used to login / logout users
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

# Login screen
login = html.Div([dcc.Location(id='url_login', refresh=True),
                  html.H2('''Please log in to continue:''', id='h1'),
                  dcc.Input(placeholder='Enter your username',
                            type='text', id='uname-box'),
                  dcc.Input(placeholder='Enter your password',
                            type='password', id='pwd-box'),
                  html.Button(children='Login', n_clicks=0,
                              type='submit', id='login-button'),
                  html.Div(children='', id='output-state'),
                  html.Br(),
                  dcc.Link('Home', href='/')])

# Successful login
success = html.Div([html.Div([html.H2('Login successful.'),
                              html.Br(),
                              dcc.Link('Home', href='/')])  # end div
                    ])  # end div

# Failed Login
failed = html.Div([html.Div([html.H2('Log in Failed. Please try again.'),
                             html.Br(),
                             html.Div([login]),
                             dcc.Link('Home', href='/')
                             ])  # end div
                   ])  # end div

# logout
logout = html.Div([html.Div(html.H2('You have been logged out - Please login')),
                   html.Br(),
                   dcc.Link('Home', href='/')
                   ])  # end div


# Callback function to login the user, or update the screen if the username or password are incorrect


@app.callback(
    [Output('url_login', 'pathname'), Output('output-state', 'children')], [Input('login-button', 'n_clicks')], [State('uname-box', 'value'), State('pwd-box', 'value')])
def login_button_click(n_clicks, username, password):
    if n_clicks > 0:
        if username == 'test' and password == 'test':
            user = User(username)
            login_user(user)
            return '/success', ''
        else:
            return '/login', 'Incorrect username or password'
    
    return dash.no_update, dash.no_update  # Return a placeholder to indicate no update
 

# Simple User class
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Initialize session tracking file
LOG_FILE = 'user_sessions.csv'

# Create the log file if it doesn't exist
try:
    pd.read_csv(LOG_FILE)
except FileNotFoundError:
    pd.DataFrame(columns=['username', 'login_time', 'logout_time', 'session_duration']).to_csv(LOG_FILE, index=False)


# Dash app setup

index_page = html.Div([
    dcc.Link('Go to Page 1', href='/page-1'),
    html.Br(),
    dcc.Link('Go to Page 2', href='/page-2'),
])


@app.callback(
    [ Output('redirect', 'pathname')],
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """Dynamic callback to display the correct page, with login protection."""

    # Default view and URL (no redirect)
    view = None
    url = no_update

    if pathname == '/login':
        view = login  # your login page layout
    elif pathname == '/success':
        if current_user.is_authenticated:
            view = success  # success page after login
        else:
            view = failed  # failed page for non-auth users
    elif pathname == '/logout':
        if current_user.is_authenticated:
            logout_user()
            view = logout  # logout page
        else:
            view = login
            url = '/login'

    # Check if pathname is a valid Dash page (registered in dash.page_registry)
    elif pathname in dash.page_registry:

        # Optional: List of pages that require login (could be stored in a set)
        protected_pages = ['/page-2', '/page-3']

        if pathname in protected_pages and not current_user.is_authenticated:
            # Redirect to login if not authenticated
            view = html.Div('Redirecting to login...')
            url = '/login'
        else:
            # Load page normally
            view = dash.page_registry[pathname]['layout']

    else:
        view = index_page  # your default index layout

    return view, url


@app.callback(Output('user-status-div', 'children'), Output('login-status', 'data'), [Input('url', 'pathname')])
def login_status(url):
    ''' callback to display login/logout link in the header '''
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated \
            and url != '/logout':  # If the URL is /logout, then the user is about to be logged out anyways
        return dcc.Link('logout', href='/logout'), current_user.get_id()
    else:
        return dcc.Link('login', href='/login'), 'loggedout'


if __name__ == '__main__':
    app.run_server(debug=True)





    

# @app.callback(Output('page-content', 'children'), Output('redirect', 'pathname'),
#               [Input('url', 'pathname')])
# def display_page(pathname):
#     ''' callback to determine layout to return '''
#     # We need to determine two things for everytime the user navigates:
#     # Can they access this page? If so, we just return the view
#     # Otherwise, if they need to be authenticated first, we need to redirect them to the login page
#     # So we have two outputs, the first is which view we'll return
#     # The second one is a redirection to another page is needed
#     # In most cases, we won't need to redirect. Instead of having to return two variables everytime in the if statement
#     # We setup the defaults at the beginning, with redirect to dash.no_update; which simply means, just keep the requested url
#     view = None
#     url = dash.no_update
#     if pathname == '/login':
#         view = login
#     elif pathname == '/success':
#         if current_user.is_authenticated:
#             view = success
#         else:
#             view = failed
#     elif pathname == '/logout':
#         if current_user.is_authenticated:
#             logout_user()
#             view = logout
#         else:
#             view = login
#             url = '/login'

#     elif pathname == '/page-1':
#         view = page_1_layout
#     elif pathname == '/page-2':
#         if current_user.is_authenticated:
#             view = page_2_layout
#         else:
#             view = 'Redirecting to login...'
#             url = '/login'
#     else:
#         view = index_page
#     # You could also return a 404 "URL not found" page here
#     return view, url




# page_1_layout = html.Div([
#     html.H1('Page 1'),
#     dcc.Dropdown(
#         id='page-1-dropdown',
#         options=[{'label': i, 'value': i} for i in ['LA', 'NYC', 'MTL']],
#         value='LA'
#     ),
#     html.Div(id='page-1-content'),
#     html.Br(),
#     dcc.Link('Go to Page 2', href='/page-2'),
#     html.Br(),
#     dcc.Link('Go back to home', href='/'),
# ])


# @app.callback(Output('page-1-content', 'children'),
#               [Input('page-1-dropdown', 'value')])
# def page_1_dropdown(value):
#     return 'You have selected "{}"'.format(value)


# page_2_layout = html.Div([
#     html.H1('Page 2'),
#     dcc.RadioItems(
#         id='page-2-radios',
#         options=[{'label': i, 'value': i} for i in ['Orange', 'Blue', 'Red']],
#         value='Orange'
#     ),
#     html.Div(id='page-2-content'),
#     html.Br(),
#     dcc.Link('Go to Page 1', href='/page-1'),
#     html.Br(),
#     dcc.Link('Go back to home', href='/')
# ])