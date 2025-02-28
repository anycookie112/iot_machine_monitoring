import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, Input, Output, State,callback
import dash_ag_grid as dag
import pandas as pd
from efficiency import calculate_downtime_df



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
        columnDefs = [{"field": col} for col in self.df_info.columns]
        return dag.AgGrid(
            id=f"machine-specific-data-{self.page}",  # Unique ID per page
            rowData=self.df_info.to_dict("records"),
            dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
            columnDefs=columnDefs,
            columnSize="sizeToFit",
        )

    def input_section(self):
        return dbc.Card([
            dbc.CardHeader("Info"),
            dbc.CardBody([
                html.P("Selected Machine Code:"),
                # html.H5(id=f"selected-machine-code-{self.page}", children="None", className="text-primary"),  
                html.Div(id=f'selected-machine-code-{self.page}'),  
                html.Div(id=f'times-stopped-{self.page}'),  
                self.grid_information()
            ])
        ], className="mt-4")

    def register_callbacks(self, app):
        """ Register the Dash callbacks dynamically. """
        @app.callback(
            Output(f"machine-specific-data-{self.page}", "rowData"),  # Unique ID per page
            Output(f'selected-machine-code-{self.page}', "children"),  # Unique ID per page
            Output(f'times-stopped-{self.page}', 'children'),  # Unique ID per page
            Input(f'machine-{self.page}-data', 'selectedRows'),  # Unique ID per page
            prevent_initial_call=True
        )
        def select_data(selected_row):
            print("test")
            if not selected_row:
                return [], "", ""  

            part = selected_row[0]
            mp_id = part.get('mp_id')  
            machine_id = part.get('machine_code', "")  

            if not mp_id:
                return [], f'Machine ID: {machine_id}', ""

            updated_data = calculate_downtime_df(mp_id)  
            times_stopped = len(updated_data.index)

            return updated_data.to_dict("records"), f'Machine ID: {machine_id}', f'Times machine stopped: {times_stopped}'

    

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

import pandas as pd
df = pd.DataFrame({'machine_code': ['A1', 'B2'], 'mp_id': [123, 456]})
df_info = pd.DataFrame({'column1': [1, 2], 'column2': [3, 4]})

# Create multiple instances with unique `page` identifiers
output_realtime = OutputInfo("test", df, df_info)
# output_history = OutputInfo("history", df, df_info)

# Register callbacks
output_realtime.register_callbacks(app)
# output_history.register_callbacks(app)

app.layout = dbc.Container([
    output_realtime.input_section(),
    output_realtime.grid_selection()
])

if __name__ == "__main__":
    app.run_server(debug=True)
