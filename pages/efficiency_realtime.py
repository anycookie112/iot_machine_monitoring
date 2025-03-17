import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, html
import dash_ag_grid as dag
import dash
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df, calculate_downtime
from config.config import DB_CONFIG

db_connection_str = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

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
    with db_connection_str.connect() as connection:
        df = pd.read_sql(query, connection)
    data_excluded = df.drop(columns=['status', 'time_completed'], errors='ignore')
    return data_excluded

dash.register_page(__name__, path='/page-3')

df = fetch_data()
outliers_df, full_df = calculate_downtime_df(46)  # Unpack the tuple

df_info = pd.DataFrame(columns=full_df.columns)  # Use full_df.columns instead

page = "realtime"

grid_selection = dag.AgGrid(
            id=f"machine-{page}-data",  # Unique ID per page
            rowData=df.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=[{"field": i} for i in df.columns],
            columnSize="sizeToFit",
        )


columnDefs = [
            { 'field': 'idmonitoring'},
            { 'field': 'date', 'filter': 'agDateColumnFilter'},
            { 'field': 'time'},
            {'field': 'time_taken' ,'filter': 'agNumberColumnFilter'},
            # {'field': 'cycle_time'},
            # {'field': 'downtime'},
            ]

grid_information = dag.AgGrid(
            id=f"machine-specific-data-{page}",  # Unique ID per page
            rowData=df_info.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=columnDefs,
            columnSize="sizeToFit",
            enableEnterpriseModules=True,  # Enables advanced features
        )
input_section = dbc.Card([
            dbc.CardHeader("Machine Details", className="bg-primary text-white fw-bold"),
            dbc.CardBody([
                
                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Machine Code", className="fw-bold"),
                        html.Div(id=f'selected-machine-code-{page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Mould Code", className="fw-bold"),
                        html.Div(id=f'mould-code-{page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Part Code", className="fw-bold"),
                        html.Div(id=f'part-code-{page}', className="text-primary")
                    ]), width=4), 
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Avg Cycle Time", className="fw-bold"),
                        html.Div(id=f'avg-cycle-time-{page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Production Start", className="fw-bold"),
                        html.Div(id=f'prod-start-time-{page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Production End", className="fw-bold"),
                        html.Div(id=f'prod-end-time-{page}', className="text-primary")
                    ]), width=4),
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Times Stopped", className="fw-bold"),
                        html.Div(id=f'times-stopped-{page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Total Downtime", className="fw-bold"),
                        html.Div(id=f'total-time-stopped-{page}', className="text-primary")
                    ]), width=4),

                    dbc.Col(html.Div([
                        html.H6("Total Shots", className="fw-bold"),
                        html.Div(id=f'num_shots-{page}', className="text-primary")
                    ]), width=4),
                ], className="mb-3"),

                html.Hr(),
                html.H5("Monitoring Data", className="fw-bold text-center mt-3"),

                
                dcc.RangeSlider(
                    min=0,
                    max=100,
                    value=[0,100],
                    step= 1,
                    id=f'time-taken-slider-{page}',
                    tooltip={"placement": "bottom", "always_visible": True}
                ),  

                grid_information
            ])
        ], className="mt-4 shadow-lg border-0")

refresh = dcc.Interval(id=f"{page}-refresh", interval=10*1000, n_intervals=0)
# refresh = dcc.Interval(id=f"{page}-refresh", n_intervals=-1)
refresh_button = dbc.Button("Refresh Data", id=f"{page}-refresh-btn", n_clicks=0)


layout = dbc.Container([
    refresh_button,
    navbar,
    grid_selection, 
    input_section,
])

@callback(
    Output(f"machine-{page}-data", "rowData"),
    Input(f"{page}-refresh-btn", "n_clicks"),
    prevent_initial_call=True
)
def refresh_table(n_clicks):
    updated_data = fetch_data()
    return updated_data.to_dict("records") 





@callback(
    Output(f"machine-specific-data-{page}", "rowData"),  
    Output(f'selected-machine-code-{page}', "children"), 
    Output(f'mould-code-{page}', "children"), 
    Output(f'part-code-{page}', "children"),  
    Output(f'times-stopped-{page}', 'children'),  
    Output(f"total-time-stopped-{page}", "children"),  
    Output(f"avg-cycle-time-{page}", "children"),  
    Output(f'prod-start-time-{page}', "children"), 
    Output(f'prod-end-time-{page}', "children"),  
    Output(f'num_shots-{page}', "children"),  
    Output(f"time-taken-slider-{page}", "max"),  
    Output(f"time-taken-slider-{page}", "min"),  
    Input(f"machine-{page}-data", 'selectedRows'),  
    Input(f"time-taken-slider-{page}", "value"),  
    prevent_initial_call=True
)

def select_data(selected_row, slider_range):
    if not selected_row:
        return [], "", "", "", "", "", "", "", "", "", 0, 0

    part = selected_row[0] if selected_row else {}
    mp_id = part.get('mp_id')  
    machine_id = part.get('machine_code', "")

    if not mp_id:
        return [], f'Machine ID: {machine_id}', "", "", "", "", "", "", "", "", 0, 0


    try:
        with db_connection_str.connect() as connection:
            query = "SELECT * FROM machine_monitoring.monitoring WHERE mp_id = %s"
            df = pd.read_sql(query, connection, params=(mp_id,))
            
            query_mould = "SELECT mp.*, mm.* FROM machine_monitoring.mass_production AS mp LEFT JOIN machine_monitoring.mould_list AS mm  ON mp.mould_id = mm.mould_code WHERE mp.mp_id = %s;"
            df_mould = pd.read_sql(query_mould, connection, params=(mp_id,))
            mould_id = df_mould.at[0, 'mould_code']
            part_code = df_mould.at[0, 'part_code']

    except Exception as e:
        print(f"Database Query Error: {e}")
        return [], f'Machine ID: {machine_id}', "Error fetching data", "", "", "", "", "", "", "", 0, 0

    # Compute downtime information
    try:
        outliers_df, full_df = calculate_downtime_df(mp_id)  
        downtime_information = calculate_downtime(mp_id)
        downtime_value = downtime_information['downtime']
        times_stopped = len(outliers_df.index) if not outliers_df.empty else 0
    except Exception as e:
        print(f"Error in calculate_downtime_df: {e}")
        return [], f'Machine ID: {machine_id}', "Error processing data", "", "", "", "", "", "", "", 0, 0
    finally:
        connection.close()

    # 🔹 Get min and max values for slider
    if "time_taken" in outliers_df:
        min_time = outliers_df["time_taken"].min()
        max_time = outliers_df["time_taken"].max()
    else:
        min_time, max_time = 0, 0  # Default values if column is missing

    # 🔹 Apply Slider Filter on 'time_taken'
    min_slider, max_slider = slider_range
    filtered_df = outliers_df[(outliers_df['time_taken'] >= min_slider) & (outliers_df['time_taken'] <= max_slider)]

    # 🔹 Return updated table and info
    return (
        filtered_df.to_dict("records"),  # 🔹 Return filtered data
        f'Machine ID: {machine_id}', 
        f'Mould code: {mould_id}', 
        f'Part code: {part_code}', 
        f'Times machine stopped: {len(outliers_df.index)}',  
        f'Total time stopped: {downtime_value}',  
        f'Avg cycle time: {round(full_df["time_taken"].median(), 2)}', 
        f'Start time: {full_df["time_input"].min() if "time_input" in full_df else "N/A"}',  
        f'End time: {full_df["time_input"].max() if "time_input" in full_df else "N/A"}',  
        f'Number Of Shots: {len(full_df.index)}',  
        max_time,  
        min_time  
    )


