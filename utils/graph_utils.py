import pandas as pd

from utils.efficiency import calculate_downtime


def daily(mp_id):
    df, _ = calculate_downtime(mp_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "total_stops"])

    df_day = df.copy()
    df_day["date"] = pd.to_datetime(df_day["time_input"]).dt.date

    filtered_df_date = df_day[df_day["action"] == "downtime"]
    df_counts = filtered_df_date.groupby("date").size().reset_index(name="total_stops")
    return df_counts


def hourly(date, mp_id=60):
    df, _ = calculate_downtime(mp_id)
    if df is None or df.empty:
        target_date = pd.to_datetime(f"{date}").date()
        return pd.DataFrame({"hour": range(1, 24), "stops": 0}), target_date

    df_hour = df.copy()
    df_hour["time_input"] = pd.to_datetime(df_hour["time_input"])
    df_hour["hour"] = df_hour["time_input"].dt.hour
    df_hour["date"] = df_hour["time_input"].dt.date

    filtered_df_hour = df_hour[df_hour["action"] == "downtime"]
    target_date = pd.to_datetime(f"{date}").date()
    filtered_df = filtered_df_hour.loc[(filtered_df_hour["date"] == target_date)]

    hourly_counts = filtered_df.groupby("hour").size().reset_index(name="stops")
    all_hours = pd.DataFrame({"hour": range(1, 24)})
    hourly_counts = all_hours.merge(hourly_counts, on="hour", how="left").fillna(0)

    return hourly_counts, target_date
