import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df, calculate_downtime

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



class OutputInfo:
    def __init__(self, page, df, df_info):
        self.page = page  # Ensure unique identifier per instance
        self.df = df
        self.df_info = df_info
    
    def grid_selection(self):
        return dag.AgGrid(
            id=f"machine-{self.page}-data",  # Unique ID per page
            rowData=self.df.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=[{"field": i} for i in self.df.columns],
            columnSize="sizeToFit",
        )

    def grid_information(self):
        columnDefs = [
            { 'field': 'idmonitoring'},
            { 'field': 'date'},
            { 'field': 'time'},
            {'field': 'time_taken'},
            {'field': 'cycle_time'},
            {'field': 'downtime'},
            ]
        return dag.AgGrid(
            id=f"machine-specific-data-{self.page}",  # Unique ID per page
            rowData=self.df_info.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=columnDefs,
            columnSize="sizeToFit",
        )

    def input_section(self):
        return dbc.Card([
            dbc.CardHeader("Machine Details", className="bg-primary text-white fw-bold"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Machine Code", className="fw-bold"),
                        html.Div(id=f'selected-machine-code-{self.page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Mould Code", className="fw-bold"),
                        html.Div(id=f'mould-code-{self.page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Part Code", className="fw-bold"),
                        html.Div(id=f'part-code-{self.page}', className="text-primary")
                    ]), width=4),
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Avg Cycle Time", className="fw-bold"),
                        html.Div(id=f'avg-cycle-time-{self.page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Production Start", className="fw-bold"),
                        html.Div(id=f'prod-start-time-{self.page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Production End", className="fw-bold"),
                        html.Div(id=f'prod-end-time-{self.page}', className="text-primary")
                    ]), width=4),
                ], className="mb-3"),

                dbc.Row([
                    dbc.Col(html.Div([
                        html.H6("Times Stopped", className="fw-bold"),
                        html.Div(id=f'times-stopped-{self.page}', className="text-primary")
                    ]), width=4),
                    
                    dbc.Col(html.Div([
                        html.H6("Total Downtime", className="fw-bold"),
                        html.Div(id=f'total-time-stopped-{self.page}', className="text-primary")
                    ]), width=4),

                    dbc.Col(html.Div([
                        html.H6("Total Shots", className="fw-bold"),
                        html.Div(id=f'num_shots-{self.page}', className="text-primary")
                    ]), width=4),
                ], className="mb-3"),

                html.Hr(),
                html.H5("Monitoring Data", className="fw-bold text-center mt-3"),
                self.grid_information()
            ])
        ], className="mt-4 shadow-lg border-0")

    def refresh(self):
        return dcc.Interval(id=f"{self.page}-refresh", n_intervals=-1)

    def register_callbacks(self):
        app = dash.get_app()  # Get the Dash app instance

        @app.callback(
            Output(f"machine-specific-data-{self.page}", "rowData"),  
            Output(f'selected-machine-code-{self.page}', "children"), 
            Output(f'mould-code-{self.page}', "children"), 
            Output(f'part-code-{self.page}', "children"),  
            Output(f'times-stopped-{self.page}', 'children'),  
            Output(f"total-time-stopped-{self.page}", "children"),  
            Output(f"avg-cycle-time-{self.page}", "children"),  
            Output(f'prod-start-time-{self.page}', "children"), 
            Output(f'prod-end-time-{self.page}', "children"),  
            Output(f'num_shots-{self.page}', "children"),  
            Input(f"machine-{self.page}-data", 'selectedRows'),  
            # Input(f"{self.page}-refresh", 'n_intervals'),
            prevent_initial_call=True
        )
        def select_data(selected_row):
            if not selected_row:
                return [], "", "", "", "", "", "", "", "", ""

            # Extract part details safely
            part = selected_row[0] if selected_row else {}
            mp_id = part.get('mp_id')  
            machine_id = part.get('machine_code', "")

            if not mp_id:  # 🔴 Fix: Avoids querying with an invalid mp_id
                return [], f'Machine ID: {machine_id}', "", "", "", "", "", "", "", ""

            # Establish database connection
            db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
            db_engine = create_engine(db_connection_str)

            # Query database
            try:
                with db_engine.connect() as connection:
                    query = "SELECT * FROM machine_monitoring.monitoring WHERE mp_id = %s"
                    # df = pd.read_sql(query, connection, params=[mp_id])
                    df = pd.read_sql(query, connection, params=(mp_id,))
                    
                    query_mould = "SELECT mp.*, mm.* FROM machine_monitoring.mass_production AS mp LEFT JOIN machine_monitoring.mould_masterlist AS mm  ON mp.mould_id = mm.mould_code WHERE mp.mp_id = %s;"
                    df_mould = pd.read_sql(query_mould, connection, params=(mp_id,))
                    mould_id = df_mould.at[0, 'mould_code']
                    part_code = df_mould.at[0, 'part_code']

            except Exception as e:
                print(f"Database Query Error: {e}")
                return [], f'Machine ID: {machine_id}', "Error fetching data", "", "", "", "", "", "", ""

            # Compute downtime information
            try:
                updated_data = calculate_downtime_df(mp_id)  
                downtime_information = calculate_downtime(mp_id)
                downtime_value = downtime_information['downtime']
                times_stopped = len(updated_data.index) if not updated_data.empty else 0
            except Exception as e:
                print(f"Error in calculate_downtime_df: {e}")
                return [], f'Machine ID: {machine_id}', "Error processing data", "", "", "", "", "", "", ""

            # Returning relevant calculated values
            return (
                updated_data.to_dict("records"), 
                f'Machine ID: {machine_id}', 
                f'Mould code: {mould_id}', 
                f'Part code: {part_code}', 
                f'Times machine stopped: {times_stopped}', #done
                f'Total time stopped: {downtime_value}', #done
                f'Avg cycle time: {round(updated_data["time_taken"].mean(), 2)}',
                f'Start time: {updated_data["time_input"].min() if "time_input" in updated_data else "N/A"}', #done
                f'End time: {updated_data["time_input"].max() if "time_input" in updated_data else "N/A"}', #done
                f'Number Of Shots: {len(df.index)}'#done
            )

        
