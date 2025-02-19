import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output, State,callback
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df

dash.register_page(__name__, path="/all")

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
    """

    # Run query and load into a DataFrame
    with db_engine.connect() as connection:
        df = pd.read_sql(query, connection)
    data_excluded = df.drop(columns=['status', 'time_completed'], errors='ignore')
    return data_excluded

df = fetch_data()
df_info = calculate_downtime_df(41)
df_info = pd.DataFrame(columns=df_info.columns)
columnDefs = [
    { 'field': 'idmonitoring'},
     { 'field': 'date'},
     { 'field': 'time'},
      {'field': 'time_taken'},
      {'field': 'cycle_time'},
      {'field': 'downtime'},
]

# AgGrid Table
grid = dag.AgGrid(
    id="machine-all-data",
    rowData=df.to_dict("records"),
    dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
    columnDefs=[{"field": i} for i in df.columns],
    columnSize="sizeToFit",
)

grid_info = dag.AgGrid(
    id="machine-specific-data",
    rowData=df_info.to_dict("records"),
    dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
    # columnDefs=[{"field": i} for i in df_info.columns],
    columnDefs=columnDefs,
    columnSize="sizeToFit",
)


input_section = dbc.Card([
    dbc.CardHeader("Info"),
    dbc.CardBody([
        html.P("Selected Machine Code:"),
        html.H5(id="selected-machine-code", children="None", className="text-primary"),  # Display selected mould
        html.Div(id='my-output'),
        grid_info
    ])
], className="mt-4")
# need to add seelcted machine 
# time start 
# time end
# how many time stopped()


layout = html.Div([
    html.H1("Machine Output:", className="card-title"),
    navbar,
    dcc.Interval(id="refresh-all", n_intervals=-1),
    grid,
    input_section

])


@dash.callback(
    Output("machine-specific-data", "rowData"),
    Output("selected-machine-code", "children"),
    Output('my-output', 'children'),
    Input('machine-all-data', 'selectedRows'),
    prevent_initial_call=True  # Prevent callback from firing on page load
)
def select_data(selected_row):
    if not selected_row:
        return [], "", ""  # Return empty list for table and empty string for UI element

    # Extract the first selected row
    part = selected_row[0]
    mp_id = part.get('mp_id')  # Use .get() to avoid KeyError
    machine_id = part.get('machine_code', "")  # Provide default empty string

    if not mp_id:
        return [], machine_id  # Ensure two values are returned

    updated_data = calculate_downtime_df(mp_id)  # Fetch updated data from DB
    times_stopped = len(updated_data.index)
    return updated_data.to_dict("records"), machine_id, f'Times machine stopped: {times_stopped}'
