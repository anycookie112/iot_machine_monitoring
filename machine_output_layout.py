import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output
import dash_ag_grid as dag
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df, calculate_downtime
from config.config import DB_CONFIG

def fetch_data():
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
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
            { 'field': 'date', 'filter': 'agDateColumnFilter'},
            { 'field': 'time'},
            {'field': 'time_taken' ,'filter': 'agNumberColumnFilter'},
            # {'field': 'cycle_time'},
            # {'field': 'downtime'},
            ]
        return dag.AgGrid(
            id=f"machine-specific-data-{self.page}",  # Unique ID per page
            rowData=self.df_info.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=columnDefs,
            columnSize="sizeToFit",
            enableEnterpriseModules=True,  # Enables advanced features
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

                
                dcc.RangeSlider(
                    min=0,
                    max=100,
                    value=[0,100],
                    id=f'time-taken-slider-{self.page}'
                ),  # so i need to get the longest time taken and shortest time take in the table outlier
                    # maybe can be like have a bool variable, if nothing is chosen false the range is a fixed number, when true the callback will return the value
                    # i need to find out like what the df outputs, 


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
            Output(f"time-taken-slider-{self.page}", "max"),  # 🔹 Return max value for slider
            Output(f"time-taken-slider-{self.page}", "min"),  # 🔹 Return min value for slider
            Input(f"machine-{self.page}-data", 'selectedRows'),  
            Input(f"time-taken-slider-{self.page}", "value"),  # 🔹 Slider filter
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

            # Establish database connection
            db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
            db_engine = create_engine(db_connection_str)

            try:
                with db_engine.connect() as connection:
                    query = "SELECT * FROM machine_monitoring.monitoring WHERE mp_id = %s"
                    df = pd.read_sql(query, connection, params=(mp_id,))
                    
                    query_mould = "SELECT mp.*, mm.* FROM machine_monitoring.mass_production AS mp LEFT JOIN machine_monitoring.mould_masterlist AS mm  ON mp.mould_id = mm.mould_code WHERE mp.mp_id = %s;"
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
                max_time,  # 🔹 Update slider max
                min_time   # 🔹 Update slider min
            )


        # @app.callback(
        #         Output(f'selected-machine-code-{self.page}', "children", allow_duplicate=True),
        #         Input(f"machine-{self.page}-data", 'selectedRows'),
        #         Input(f'time-taken-slider-{self.page}', 'value'),
                

                
        # )

        # def range_filter(selected_row):
        #     db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
        #     db_engine = create_engine(db_connection_str)

        #     # Extract part details safely
        #     part = selected_row[0] if selected_row else {}
        #     mp_id = part.get('mp_id')  
        #     machine_id = part.get('machine_code', "")
        #     print("new call back")
        #     print(mp_id)
        #     # # Query database
        #     # try:
        #     #     with db_engine.connect() as connection:
        #     #         query = "SELECT * FROM machine_monitoring.monitoring WHERE mp_id = %s"
        #     #         # df = pd.read_sql(query, connection, params=[mp_id])
        #     #         df = pd.read_sql(query, connection, params=(mp_id,))
                    
        #     #         query_mould = "SELECT mp.*, mm.* FROM machine_monitoring.mass_production AS mp LEFT JOIN machine_monitoring.mould_masterlist AS mm  ON mp.mould_id = mm.mould_code WHERE mp.mp_id = %s;"
        #     #         df_mould = pd.read_sql(query_mould, connection, params=(mp_id,))
        #     #         mould_id = df_mould.at[0, 'mould_code']
        #     #         part_code = df_mould.at[0, 'part_code']

        #     # except Exception as e:
        #     #     print(f"Database Query Error: {e}")
        #     #     # return [], f'Machine ID: {machine_id}', "Error fetching data", "", "", "", "", "", "", ""


        #     pass
        """
        machine output include date into the columns
        need to query with the mp id
        where time taken in the range of value
        then return the filtered df back to the table
        do i need to add a refresh button for the top side of r
        the mould

        how do i get mpid
        i need to teach the people how to use
        i need to ask hamdan if my relay can be used and is my signalxorrecr
        i dont think we need machine id 
        sop selected row is also 1 of the input into this callback function
        then the mp_id will be used to query the data in the db
        the other values should be the same noprobem
        or is there a way i cant pass my mp_id info down into the duncitob

        """

        
