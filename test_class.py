from test import OutputInfo, fetch_data

import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output, State,callback
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# import pandas as pd
# df = pd.DataFrame({'machine_code': ['A1', 'B2'], 'mp_id': [123, 456]})
# df_info = pd.DataFrame({'column1': [1, 2], 'column2': [3, 4]})
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

print(df)

# Create multiple instances with unique `page` identifiers
output_realtime = OutputInfo("realtime", df, df_info)


# Register callbacks
output_realtime.register_callbacks(app)


app.layout = dbc.Container([
    output_realtime.grid_selection(),
    output_realtime.input_section(),
])

if __name__ == "__main__":
    app.run_server(debug=True)
