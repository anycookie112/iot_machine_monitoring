import dash_bootstrap_components as dbc
import dash
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd
from machine_output_layout import OutputInfo
from utils.efficiency import calculate_downtime_df
from config.config import MQTT_CONFIG, DB_CONFIG

dash.register_page(__name__, path="/recent")

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
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
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
outliers_df, full_df = calculate_downtime_df(41)  # Unpack the tuple
df_info = pd.DataFrame(columns=full_df.columns)  # Use full_df.columns instead

# Create multiple instances with unique `page` identifiers
output_realtime = OutputInfo("recent", df, df_info)
# output_history = OutputInfo("history", df, df_info)

# Register callbacks
output_realtime.register_callbacks()


layout = dbc.Container([
    navbar,
    output_realtime.grid_selection(), 
    output_realtime.input_section(),
    output_realtime.refresh(),
])

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