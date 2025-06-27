# import dash_bootstrap_components as dbc
# from dash import html, dcc, Input, Output, callback, callback_context
# import dash_ag_grid as dag
# import dash
# from sqlalchemy import create_engine
# import pandas as pd
# import os
# import datetime
# from datetime import datetime, timedelta, date
# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# from utils.daily import fetch_data_monthly, monthly
# from config.config import DB_CONFIG
# import plotly.graph_objects as go
# import plotly.express as px

# dash.register_page(__name__, path="/monthly")


# page = "monthly"

# # Generate bar chart for machine stops
# def generate_bar_chart(data_frame, title):
#     """
#     Generate a bar chart showing the monthly report.

#     Args:
#         data_frame (pd.DataFrame): DataFrame containing the data.
#         title (str): Title of the bar chart.

#     Returns:
#         plotly.graph_objects.Figure: The generated bar chart.
#     """
#     fig = px.bar(
#         data_frame,
#         x="machine_code",
#         y="month_total_stop",  # Use the correct column name
#         title=title,
#         labels={"machine_code": "Machine Code", "month_total_stop": "Total Stops"},
#         text="month_total_stop",  # Update this as well
#     )
#     # fig.update_traces(textposition="outside")
#     fig.update_layout(
#         xaxis_title="Machine Code",
#         yaxis_title="Total Stops",
#         title_x=0.5,
#     )
#     return fig



# # Generate bar chart for machine stops
# def generate_bar_chart_shift(shift_data, title):
#     """
#     Generate a bar chart showing the number of stops for each hour in a shift.

#     Args:
#         shift_data (pd.DataFrame): DataFrame containing 'hour' and 'stops' columns.
#         title (str): Title of the bar chart.

#     Returns:
#         dcc.Graph: Dash Graph component with the bar chart.
#     """
#     # Convert hour to string to prevent automatic sorting by number
#     # shift_data["hour_str"] = shift_data["hour"].astype(str)

#     fig = px.bar(
#         shift_data,
#         x="day",
#         y="stops",
#         title=title,
#         labels={"days": "Day Of The Month", "stops": "Number of Stops"},
#         text="stops",
#         # category_orders={"hour_str": shift_data["hour_str"].tolist()}  # maintain order
#     )

#     # fig.update_traces(textposition="outside")
#     fig.update_layout(
#         xaxis_title="Day Of The Month",
#         yaxis_title="Total Stops",
#         title_x=0.5,
#         xaxis=dict(type="category")  # force categorical axis to preserve order
#     )

#     return fig




# df_report = fetch_data_monthly()
# monthly_data = monthly('A6')

# # yesterday_date_8am = (datetime.now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
# # current_date_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
# monthly_report_graph = generate_bar_chart(df_report, f"Monthly Report")

# daily_graph = generate_bar_chart_shift(monthly_data, "Daily Stops")


# grid_monthly = dag.AgGrid(
#     id="grid_monthly",
#     rowData=df_report.to_dict("records"),
#     dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
#     columnDefs=[
#         {
#             "field": i,
#             "wrapHeaderText": True,
#             "autoHeaderHeight": True
#         } for i in [
#             "machine_code", "month_total_stop", "month_total_dt"
            
#         ]
#     ],
#     columnSize="autoSize",
# )


# refresh = dcc.Interval(
#     id="refresh-interval",
#     interval= 3600 * 1000,  # 5 seconds
#     n_intervals=0,
# )

# refresh_button = dbc.Button(
#     "Refresh Data",
#     id="refresh-button",
#     color="primary",
#     className="mb-3",
# )


# layout = html.Div([
#     html.H1(
#         "Daily Report Analysis",
#         style={"textAlign": "center", "marginBottom": "20px", "color": "#2c3e50"}
#     ),

#     # Date Picker Section
#     html.Div([
#     html.Label("Select Month & Year:", style={"fontWeight": "bold", "marginRight": "10px"}),

#         dcc.Dropdown(
#             id='month-picker',
#             options=[{"label": f"{month:02d}", "value": month} for month in range(1, 13)],
#             placeholder="Month",
#             style={"width": "100px", "display": "inline-block", "marginRight": "10px"}
#         ),

#         dcc.Dropdown(
#             id='year-picker',
#             options=[{"label": str(y), "value": y} for y in range(2025, datetime.now().year + 1)],
#             placeholder="Year",
#             style={"width": "100px", "display": "inline-block"}
#         )
#     ], style={"textAlign": "center", "marginBottom": "20px"}),

#     # Refresh Button and Daily Report Graph
#     html.Div([
#         html.Div(refresh_button, style={"textAlign": "center", "marginBottom": "20px"}),
#         dcc.Graph(id = "monthly_report", figure=monthly_report_graph),
#     ]),
#     # Shift Graphs Section
#     html.Div([
#         html.Div(
#             dcc.Graph(id="daily-graph", figure=daily_graph),
#         style={
#             "width": "100%",  # Set the width to 100% to make the graph extend fully
#             "display": "block",  # Use block display for full-width alignment
#             "padding": "10px",
#             "boxShadow": "0px 4px 6px rgba(0, 0, 0, 0.1)",
#             "borderRadius": "10px"
#         }        ),
#     ]),

#     # Data Grid Section
#     html.Div([
#         html.H3("Daily Report Data", style={"textAlign": "center", "marginBottom": "20px"}),
#         grid_monthly,
#     ], className="mb-4", style={"padding": "20px", "border": "1px solid #ddd", "borderRadius": "10px", "backgroundColor": "#f9f9f9"}),

    
# ], style={"padding": "20px", "fontFamily": "Arial, sans-serif", "backgroundColor": "#f4f6f9"})


# @callback(
#     Output("daily-graph", "figure"),  
#     Input("monthly_report", 'clickData'),  
# )
# def update_shift_data(clickData):
#     if clickData is None:
#         return go.Figure()  # ✅ Return an empty figure instead of a string
#     machine_code = clickData["points"][0]["x"]  # Ensure this matches the format in your DataFrame
#     print(machine_code)
#     monthly_data = monthly(machine_code)
#     daily_graph = generate_bar_chart_shift(monthly_data, "Daily Stops")
#     return daily_graph

#     # if clickData is not None:


#     # app.run_server(port=8888)


        
    
#     #     machine_code = clickData["points"][0]["x"]
#     #     update_daily = monthly(machine_code, datetime.now())
#     #     print(machine_code)  # Debugging line to check selected machine code
#     #     return update_daily.to_dict("records")  # Update the grid with new data
    
#     # return []






    
