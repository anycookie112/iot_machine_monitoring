import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, callback_context
import dash_ag_grid as dag
import dash
from sqlalchemy import create_engine
import pandas as pd
import os
import datetime
from datetime import datetime, timedelta, date
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.daily import daily_report, hourly
from config.config import DB_CONFIG
import plotly.graph_objects as go
import plotly.express as px

dash.register_page(__name__, path="/daily")


page = "daily"

# Generate bar chart for machine stops
def generate_bar_chart(shift_data, title):
    """
    Generate a bar chart showing the number of stops for each machine.

    Args:
        shift_data (pd.DataFrame): DataFrame containing shift data.
        title (str): Title of the bar chart.

    Returns:
        dcc.Graph: Dash Graph component with the bar chart.
    """
    fig = px.bar(
        shift_data,
        x="machine_code",
        y="total_stops",
        title=title,
        labels={"machine_code": "Machine Code", "total_stops": "Total Stops"},
        text="total_stops",
    )
    # fig.update_traces(textposition="outside")
    # fig.update_layout(
    #     xaxis_title="Machine Code",
    #     yaxis_title="Total Stops",
    #     title_x=0.5,
    # )
    return fig

# Generate bar chart for machine stops
def generate_bar_chart_shift(shift_data, title):
    """
    Generate a bar chart showing the number of stops for each hour in a shift.

    Args:
        shift_data (pd.DataFrame): DataFrame containing 'hour' and 'stops' columns.
        title (str): Title of the bar chart.

    Returns:
        dcc.Graph: Dash Graph component with the bar chart.
    """
    # Convert hour to string to prevent automatic sorting by number
    shift_data["hour_str"] = shift_data["hour"].astype(str)

    fig = px.bar(
        shift_data,
        x="hour_str",
        y="stops",
        title=title,
        labels={"hour_str": "Hour of the Day", "stops": "Number of Stops"},
        text="stops",
        category_orders={"hour_str": shift_data["hour_str"].tolist()}  # maintain order
    )

    # fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_title="Hour of the Day",
        yaxis_title="Total Stops",
        title_x=0.5,
        xaxis=dict(type="category")  # force categorical axis to preserve order
    )

    return fig


shift1, shift2 = hourly(79)

df_report = daily_report()

yesterday_date_8am = (datetime.now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
current_date_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
daily_report_graph = generate_bar_chart(df_report, f"Daily Report ({yesterday_date_8am})-({current_date_8am})")

bar_chart_shift_1 = generate_bar_chart_shift(shift1, "Shift 1: Machine Stops (0800 - 2000)")
bar_chart_shift_2 = generate_bar_chart_shift(shift2, "Shift 2: Machine Stops (2000 - 0800)")


grid_daily = dag.AgGrid(
    id="grid_daily",
    rowData=df_report.to_dict("records"),
    dashGridOptions={'rowSelection': 'single', 'defaultSelected': [0]},
    columnDefs=[
        {
            "field": i,
            "wrapHeaderText": True,
            "autoHeaderHeight": True
        } for i in [
            "mp_id", "machine_code", 'mould_id',
            'shift_1_stops', 'shift_1_downtime',
            'shift_2_stops', 'shift_2_downtime',
            'min_cycle_time', 'median_cycle_time',
            'max_cycle_time', 'variance'
        ]
    ],
    columnSize="autoSize",
)


refresh = dcc.Interval(
    id="refresh-interval",
    interval= 3600 * 1000,  # 5 seconds
    n_intervals=0,
)

refresh_button = dbc.Button(
    "Refresh Data",
    id="refresh-button",
    color="primary",
    className="mb-3",
)


layout = html.Div([
    html.H1(
        "Daily Report Analysis",
        style={"textAlign": "center", "marginBottom": "20px", "color": "#2c3e50"}
    ),

    # Date Picker Section
    html.Div([
        html.Label("Select Date:", style={"fontWeight": "bold", "marginRight": "10px"}),
        dcc.DatePickerSingle(
            id='date-picker',
            display_format='YYYY-MM-DD',
            date=datetime.now().date(),  # Default to today
            style={"marginBottom": "20px"}
        ),
    ], style={"textAlign": "center", "marginBottom": "20px"}),

    # Refresh Button and Daily Report Graph
    html.Div([
        html.Div(refresh_button, style={"textAlign": "center", "marginBottom": "20px"}),
        dcc.Graph(id = "overall_report", figure=daily_report_graph),
    ]),

    # Data Grid Section
    html.Div([
        html.H3("Daily Report Data", style={"textAlign": "center", "marginBottom": "20px"}),
        grid_daily,
    ], className="mb-4", style={"padding": "20px", "border": "1px solid #ddd", "borderRadius": "10px", "backgroundColor": "#f9f9f9"}),

    # Shift Graphs Section
    html.Div([
        html.Div(
            dcc.Graph(id="shift1-graph", figure=bar_chart_shift_1),
            style={"width": "48%", "display": "inline-block", "padding": "10px", "boxShadow": "0px 4px 6px rgba(0, 0, 0, 0.1)", "borderRadius": "10px"}
        ),
        html.Div(
            dcc.Graph(id="shift2-graph", figure=bar_chart_shift_2),
            style={"width": "48%", "display": "inline-block", "padding": "10px", "boxShadow": "0px 4px 6px rgba(0, 0, 0, 0.1)", "borderRadius": "10px"}
        ),
    ], style={"display": "flex", "justifyContent": "space-between", "gap": "4%", "marginTop": "20px"}),
], style={"padding": "20px", "fontFamily": "Arial, sans-serif", "backgroundColor": "#f4f6f9"})



@callback(
    Output("shift1-graph", "figure"),  
    Output("shift2-graph", "figure"),  
    Input("grid_daily", 'selectedRows'),  
    Input("date-picker", 'date'),  
)
def update_shift_data(selected_row, date):
    # print(selected_row)  # Debugging line to check selected rows
    parsed_date = datetime.strptime(date, "%Y-%m-%d")
    if not selected_row:  # Fix: Handle empty list or None
        return go.Figure(), go.Figure()  

    part = selected_row[0]  # Safely extract the first row
    mp_id = part.get('mp_id')  

    if mp_id is None:  # Fix: Ensure mp_id is valid
        return go.Figure(), go.Figure()  

    # Get hourly downtime data for the selected date
    shift1, shift2 = hourly(mp_id, parsed_date)  # Ensure `hourly()` returns a DataFrame

    # If there are no downtime events for the selected day, return an empty graph
    if shift1.empty or shift2.empty:
        return go.Figure(), go.Figure()  


    # Create a new bar chart for hourly downtime
    bar_chart_shift_1 = generate_bar_chart_shift(shift1, "Shift 1: Machine Stops (0800 - 2000)")
    bar_chart_shift_2 = generate_bar_chart_shift(shift2, "Shift 2: Machine Stops (2000 - 0800)")


    return bar_chart_shift_1, bar_chart_shift_2 



@callback(
    Output("grid_daily", "rowData"),  
    Output("overall_report", "figure"),  
    Input("date-picker", 'date'),  
)
def update_shift_data(date):
    if date is not None:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
        df_report = daily_report(parsed_date)

        daily_report_graph = generate_bar_chart(df_report, f"Report ({date})")


        return df_report.to_dict("records"), daily_report_graph  # Update the grid with new data
    return []
    
