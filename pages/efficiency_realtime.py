import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, callback_context
import dash_ag_grid as dag
import dash
from sqlalchemy import create_engine
import pandas as pd
from utils.efficiency import calculate_downtime_df, calculate_downtime
from config.config import DB_CONFIG
import plotly.graph_objects as go
import plotly.express as px

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
            {'field': 'action'},
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


grid_information_bar = dag.AgGrid(
            id=f"machine-bar-data-{page}",  # Unique ID per page
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
                    value=[0,10000],
                    step= 1,
                    marks = None,
                    id=f'time-taken-slider-{page}',
                    tooltip={"placement": "bottom", "always_visible": True}
                ),  
                html.Div(id=f"output-div-{page}-1"), 
                grid_information
            ])
        ], className="mt-4 shadow-lg border-0")

refresh = dcc.Interval(id=f"{page}-refresh", interval=10*1000, n_intervals=0)
# refresh = dcc.Interval(id=f"{page}-refresh", n_intervals=-1)
refresh_button = dbc.Button("Refresh Data", id=f"{page}-refresh-btn", n_clicks=0)


def daily(mp_id):
    df, dummy = calculate_downtime(mp_id)

    df_day = df

    # Convert time_input to datetime and extract only the date
    df_day["date"] = pd.to_datetime(df_day["time_input"]).dt.date

    # Filter only downtime actions
    filtered_df_date = df_day[df_day["action"] == "downtime"]
    # print(filtered_df_date)

    # Count stops per day
    df_counts = filtered_df_date.groupby("date").size().reset_index(name="total_stops")

    return df_counts

def hourly(date, mp_id):
    df, dummy = calculate_downtime(mp_id)
    df_hour = df

    df_hour["time_input"] = pd.to_datetime(df_hour["time_input"])

    # Extract the hour for grouping
    df_hour["hour"] = df_hour["time_input"].dt.hour
    df_hour["date"] = df_hour["time_input"].dt.date

    # print(f"dfhour{df_hour}")

    filtered_df_hour = df_hour[df_hour["action"].isin(["downtime"])]
    # print(f"filtered_df_hour{filtered_df_hour}")

    target_date = pd.to_datetime(f"{date}").date()

    filtered_df = filtered_df_hour.loc[(filtered_df_hour['date'] == target_date)]

    hourly_counts = filtered_df.groupby("hour").size().reset_index(name="stops")
    all_hours = pd.DataFrame({"hour": range(0, 24)})  # Ensure x-axis is 1-23
    hourly_counts = all_hours.merge(hourly_counts, on="hour", how="left").fillna(0)
    
    return hourly_counts, target_date

# Load data
mp_id = 61
df_counts = daily(mp_id)
# print("hello world")
# print(df_counts)

# df_counts = None
date = "2025-03-27"
hourly_counts, target_date = hourly(date, mp_id)
# print(hourly_counts)


############################################# BAR CHART FOR DAYS ##############################################################

# Create Plotly bar chart

fig_day = px.bar(df_counts, x="date", y="total_stops",
                title="Machine Stops Per Day",
                labels={"date": "Date", "total_stops": "Total Stops"},
                text="total_stops")


# Format X-axis for better readability
fig_day.update_xaxes(type="category")  # Ensure only available dates are shown

############################################# BAR CHART FOR HOURS ##############################################################


# Plotly bar chart
fig_hour = px.bar(
    hourly_counts, 
    x="hour", 
    y="stops",
    # title=f"Machine Downtime on {target_date}",
    title = f"{target_date}",
    labels={"hour": "Hour of the Day", "stops": "Number of Stops"},
    text="stops",
)

# Format X-axis to show hours 1-23
fig_hour.update_xaxes(tickmode="linear", dtick=1, title_text="Hour of the Day")
fig_hour.update_yaxes(title_text="Number of Stops")
fig_hour.update_traces(marker_color="red", opacity=0.7)

#################################################################################################################################




layout = html.Div([
    html.H1("Machine Stops Analysis"),
    navbar,
    refresh_button,
    grid_selection,

    input_section,
    # html.Div(id=f"output-div-{page}", style={"margin-top": "20px", "font-size": "20px"}),  # Display click data

    html.Div([
        dcc.Graph(id=f"bar_day-{page}", figure=fig_day, style={"width": "50%", "display": "inline-block"}),
        dcc.Graph(id=f"bar_hour-{page}", figure=fig_hour, style={"width": "50%", "display": "inline-block"}),
    ], style={"display": "flex", "justify-content": "space-between"}),  # Flexbox for side-by-side layout
    html.Div(id=f"output-div-{page}-2"), 
    grid_information_bar
])


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
    Output(f"output-div-{page}-1", "children"), 
    # Output(f"dropdown-{page}", "options"),  
    Input(f"machine-{page}-data", 'selectedRows'),  
    Input(f"time-taken-slider-{page}", "value"),  
    # Input("bar_hour", "clickData"),
    # Input("bar_day", "clickData"), 
    # Input("stored-day", "data"),

    prevent_initial_call=True
)

def select_data(selected_row, slider_range):
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    # print(selected_row)
    if not selected_row:
        return [], "", "", "", "", "", "", "", "", "", 0, 0, "No data available"

    part = selected_row[0] if selected_row else {}
    mp_id = part.get('mp_id')  
    machine_id = part.get('machine_code', "")

    if not mp_id:
        return [], f'Machine ID: {machine_id}', "", "", "", "", "", "", "", "", 0, 0, "No data available"

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
        return [], f'Machine ID: {machine_id}', "Error fetching data", "", "", "", "", "", "", "", 0, 0, "No data available"

    # Compute downtime information
    try:
        # outliers_df, full_df = calculate_downtime_df(mp_id)  
        df_select_data, downtime_information = calculate_downtime(mp_id)
        downtime_value = downtime_information['downtime']
        times_stopped = downtime_information['total_times_stoped']
        start_time = downtime_information['start_time']
        end_time = downtime_information['end_time']
    except Exception as e:
        print(f"Error in calculate_downtime_df: {e}")
        return [], f'Machine ID: {machine_id}', "Error processing data", "", "", "", "", "", "", "", 0, 0, "No data available"
    finally:
        connection.close()

    if "time_taken" in df_select_data:
        min_time = df_select_data["time_taken"].min()
        max_time = df_select_data["time_taken"].max()
    else:
        min_time, max_time = 0, 9999  # Default values if column is missing

    # Unpack slider safely
    if slider_range and len(slider_range) == 2:
        min_slider, max_slider = slider_range
    else:
        min_slider, max_slider = 0, 9999  # Safe fallback
    
    # Then filter by slider range (always)
    # Filter for 'downtime' action directly in the main DataFrame
    filtered_df = df_select_data.loc[
        (df_select_data['action'] == 'downtime') & 
        (df_select_data['time_taken'] >= min_slider) & 
        (df_select_data['time_taken'] <= max_slider)
    ]
    total = len(filtered_df.index)
    return (
        filtered_df.to_dict("records"),  # 🔹 Return filtered data
        f'Machine ID: {machine_id}', 
        f'Mould code: {mould_id}', 
        f'Part code: {part_code}', 
        f'Times machine stopped: {times_stopped}',  
        f'Duration machine stopped: {downtime_value}',  
        f'Avg cycle time: {downtime_information["median_cycle_time"]}', 
        f'Start time: {start_time}',  
        f'End time: {end_time}',  
        f'Number Of Shots: {downtime_information["total_shots"]}',  
        max_time + 1,  
        min_time,
        f"Total Stoped After Filter: {total}"
                )



@callback(
    Output(f"bar_day-{page}", "figure"),  # Update the hourly downtime graph
    Input(f"machine-{page}-data", 'selectedRows'),  
)
def update_day_graph(selected_row):
    if not selected_row:  # Fix: Handle empty list or None
        return go.Figure()  

    part = selected_row[0]  # Safely extract the first row
    mp_id = part.get('mp_id')  

    if mp_id is None:  # Fix: Ensure mp_id is valid
        return go.Figure()

    df_count = daily(mp_id)
    # print(df_count)

    if df_count.empty:  # Fix: Ensure there's data before plotting
        return go.Figure()

    # Create Plotly bar chart
    fig_day = px.bar(df_count, x="date", y="total_stops",
                     title="Machine Stops Per Day",
                     labels={"date": "Date", "total_stops": "Total Stops"},
                     text="total_stops")

    # Format X-axis for better readability
    fig_day.update_xaxes(type="category")

    return fig_day  # ✅ Return the updated figure


  
@callback(
    Output(f"bar_hour-{page}", "figure"),  # Update the hourly downtime graph
    Input(f"bar_day-{page}", "clickData"),  # Listen for clicks on the daily downtime graph
    Input(f"machine-{page}-data", 'selectedRows'),  
)
def update_hour_graph(clickData, selected_row):
    if not selected_row:  # Fix: Handle empty list or None
        return go.Figure()  

    part = selected_row[0]  # Safely extract the first row
    mp_id = part.get('mp_id')  

    if mp_id is None:  # Fix: Ensure mp_id is valid
        return go.Figure()

    if clickData is None:
        return go.Figure()  # ✅ Return an empty figure instead of a string

    # Extract clicked date from the bar chart
    date = clickData["points"][0]["x"]  # Ensure this matches the format in your DataFrame

    # Get hourly downtime data for the selected date
    hourly_counts, target_date = hourly(date, mp_id)  # Ensure `hourly()` returns a DataFrame

    # If there are no downtime events for the selected day, return an empty graph
    if hourly_counts.empty:
        return go.Figure()

    # Create a new bar chart for hourly downtime
    fig_hour = px.bar(
        hourly_counts,
        x="hour",
        y="stops",
        title=f"Machine Downtime on {target_date}",
        labels={"hour": "Hour of the Day", "stops": "Number of Stops"},
        text="stops",
    )

    # Format X-axis (show hours 0-23)
    fig_hour.update_xaxes(tickmode="linear", dtick=1, title_text="Hour of the Day")
    fig_hour.update_yaxes(title_text="Number of Stops")
    fig_hour.update_traces(marker_color="red", opacity=0.7)

    return fig_hour  # ✅ Return the updated figure

@callback(
    Output(f"machine-bar-data-{page}", "rowData"), 
    Output(f"output-div-{page}-2", "children"), 
    Input(f"machine-{page}-data", 'selectedRows'), 
    Input(f"bar_day-{page}", "clickData"),
    Input(f"bar_hour-{page}", "clickData")  # Optional if you're using hour later
)
def update_extra_table(selected_row, clicked_day, clicked_hour):
    # Default: No selection
    part = selected_row[0] if selected_row else {}
    mp_id = part.get('mp_id')  

    # Get the downtime data
    df_select_data, dummy = calculate_downtime(mp_id)

    

    # Initialize the day variable
    day = None
    hour = None

    # Check if clicked_day is available
    if clicked_day and "points" in clicked_day and clicked_day["points"]:
        # Extract day from the clicked day
        day = clicked_day["points"][0].get("x")
        # print(f"Selected day: {day}")

        # Convert the day to a datetime object to match the DataFrame's 'date' format
        day = pd.to_datetime(day, errors='coerce').date()  # Keep only the date part

        # Filter the DataFrame by selected day if it's a valid date
        if pd.notna(day):
            # Ensure 'date' column in df_select_data is of datetime type and compare only date part
            df_select_data['date'] = pd.to_datetime(df_select_data['date'], errors='coerce').dt.date
            df_select_data = df_select_data[(df_select_data['date'] == day) & (df_select_data['action'] == 'downtime')]
            total = len(df_select_data.index)
    # Return the filtered data for the rowData
    if clicked_hour and "points" in clicked_hour and clicked_hour["points"]:
        hour = clicked_hour["points"][0].get("x")
        # print(f"Selected day: {hour}")
    


    # Ensure the DataFrame is not empty
    if df_select_data.empty:
        return [],  "No data available"
    total = len(df_select_data)

    return (df_select_data.to_dict("records"), f"Total Times Machine Stopped: {total}")   # Return the filtered data


@callback(
    Output(f"machine-{page}-data", "rowData"),
    Input(f"{page}-refresh-btn", "n_clicks"),
    prevent_initial_call=True
)
def refresh_table(n_clicks):
    updated_data = fetch_data()
    return updated_data.to_dict("records") 