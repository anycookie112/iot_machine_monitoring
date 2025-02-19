import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output, State,callback
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd

dash.register_page(__name__, path="/recent")

import dash_bootstrap_components as dbc
from dash import html

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Running", href="/page-3")),
        dbc.NavItem(dbc.NavLink("Recent", href="/recent")),
        dbc.NavItem(dbc.NavLink("All", href="/all")),

    ],
    brand="Machine Output",
    brand_href="#",
    color="primary",
    dark=True,
)


def fetch_data():
    # Connect to the database
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    db_engine = create_engine(db_connection_str)  # Use only one connection

    # Query the database
    query = """
        select * from mass_production
        where status = "completed" 
        And time_completed >= NOW() - INTERVAL 1 DAY
    """

    # Run query and load into a DataFrame
    with db_engine.connect() as connection:
        df = pd.read_sql(query, connection)
    data_excluded = df.drop(columns=['status', 'time_completed'], errors='ignore')
    return data_excluded

df = fetch_data()

# AgGrid Table
grid = dag.AgGrid(
    id="machine-recent-data",
    rowData=df.to_dict("records"),
    dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
    columnDefs=[{"field": i} for i in df.columns],
    columnSize="sizeToFit",
)

layout = html.Div([
    html.H1("Machine Output Last 24 Hours:", className="card-title"),
    navbar,
    dcc.Interval(id="refresh-recent", interval=1500000, n_intervals=0),
    grid,

])



# Callback to refresh table data
@dash.callback(
    Output("machine-recent-data", "rowData"),
    Input("refresh-recent", 'n_intervals'),

    prevent_initial_call=True  # Prevent callback from firing on page load
)
def refresh_table(n_clicks):
    updated_data = fetch_data()  # Fetch updated data from DB
    return updated_data.to_dict("records")


"""


so when i select row , it needs to show me how many times the machine has stopped
every time between cycle >= 5

or do i just use downtime
also need to convert downtime to mins/hrs


so now i got the funciton done i just need to write the code for the selected row extract the mp_id and 
pass the value through the function
so when i click
show


how many times stopped
len of rows

longest downtime
max of column = downtime

then list all the downtime more than 5 min
what time 
the columns i need are 


idmonitoring
time takem 
time input (cycle end)
cycle time start 
downtime



"""