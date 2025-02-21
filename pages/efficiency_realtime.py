import dash_bootstrap_components as dbc
import dash
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df
from machine_output_layout import OutputInfo

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
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    db_engine = create_engine(db_connection_str)  # Use only one connection

    # Query the database
    query = """
        SELECT 
            mp.*
        FROM mass_production AS mp
        JOIN machine_list AS ml ON ml.machine_code = mp.machine_code
        WHERE ml.machine_status = 'mass prod'
        AND mp.mp_id = (
            SELECT MAX(mp_id) 
            FROM mass_production 
            WHERE machine_code = mp.machine_code
        );
    """

    # Run query and load into a DataFrame
    with db_engine.connect() as connection:
        df = pd.read_sql(query, connection)
    data_excluded = df.drop(columns=['status', 'time_completed'], errors='ignore')
    return data_excluded

dash.register_page(__name__, path='/page-3')

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

# Create multiple instances with unique `page` identifiers
output_realtime = OutputInfo("realtime", df, df_info)

# Register callbacks
output_realtime.register_callbacks()

layout = dbc.Container([
    navbar,
    output_realtime.grid_selection(), 
    output_realtime.input_section(),
    output_realtime.refresh(),
])

