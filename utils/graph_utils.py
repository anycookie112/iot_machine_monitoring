import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Output, Input, callback_context
import plotly.graph_objects as go
from config.config import DB_CONFIG
from sqlalchemy import create_engine
import dash_bootstrap_components as dbc
import dash_ag_grid as dag

from efficiency import calculate_downtime,calculate_downtime_df



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

def hourly(date):
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
    all_hours = pd.DataFrame({"hour": range(1, 24)})  # Ensure x-axis is 1-23
    hourly_counts = all_hours.merge(hourly_counts, on="hour", how="left").fillna(0)
    
    return hourly_counts, target_date

# Load data
mp_id = 60
df_counts = daily(mp_id)

# df_counts = None
date = "2025-03-27"
hourly_counts, target_date = hourly(date)


print(df_counts)