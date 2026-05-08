from datetime import datetime, timedelta
from sqlalchemy import text
import plotly.graph_objects as go
import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.efficiency import calculate_downtime
from utils.db import get_db_engine

def calculate_filtered_variance(df, column_name, threshold=1.5):
    """
    Calculate the variance of a column after filtering out extreme values using the IQR method.

    Args:
        df (pd.DataFrame): The DataFrame containing the data.
        column_name (str): The name of the column to calculate variance for.
        threshold (float): The multiplier for the IQR to define outliers (default is 1.5).

    Returns:
        float: The variance of the filtered column.
        
    """
    # Calculate Q1 (25th percentile) and Q3 (75th percentile)
    Q1 = df[column_name].quantile(0.10)
    # print(Q1)
    Q3 = df[column_name].quantile(0.90)
    # print(Q3)
    IQR = Q3 - Q1

    # Define the lower and upper bounds for filtering
    lower_bound = Q1 - threshold * IQR
    upper_bound = Q3 + threshold * IQR

    # Filter the DataFrame to exclude outliers
    filtered_df = df[(df[column_name] >= lower_bound) & (df[column_name] <= upper_bound)]

    # Calculate and return the variance of the filtered column
    return filtered_df[column_name].var()


def fetch_data_variation(date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    query = text("""
        SELECT monitoring.*, production.mould_id, production.machine_code
        FROM machine_monitoring.monitoring AS monitoring
        INNER JOIN machine_monitoring.mass_production AS production
            ON monitoring.mp_id = production.mp_id
        WHERE monitoring.time_input BETWEEN :start_time AND :end_time
        AND monitoring.action IN ('normal_cycle');
    """)

    # parsed_date = datetime.strptime(date, "%Y-%m-%d")

    start, mid , end = date_calculation(date)

    # Run query and load into a DataFrame
    with get_db_engine().connect() as connection:

        df = pd.read_sql(query, connection, params={
            "start_time": start,
            "end_time": end
        })
        # print(df)
    return df

def calculate_filtered_variance_by_group(df, group_col, target_col, threshold=1.5):
    """
    Calculate filtered variance and key percentiles of a target column per group after removing outliers.

    Args:
        df (pd.DataFrame): The input DataFrame.
        group_col (str): The column name to group by (e.g., "mp_id").
        target_col (str): The column to analyze (e.g., "time_taken").
        threshold (float): IQR multiplier to define outliers (default = 1.5).

    Returns:
        pd.DataFrame: A DataFrame with group_col, Q1, median, Q3, and filtered variance.
    """
    results = []

    for group_val, group_df in df.groupby(group_col):
        Q1 = group_df[target_col].quantile(0.05)
        median = group_df[target_col].quantile(0.50)
        Q3 = group_df[target_col].quantile(0.95)
        IQR = Q3 - Q1

        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR

        filtered = group_df[(group_df[target_col] >= lower_bound) & (group_df[target_col] <= upper_bound)]
        variance = filtered[target_col].var()
        variance = 0 if pd.isna(variance) else variance

        results.append({
            group_col: group_val,
            "min_cycle_time": round(Q1, 2),
            "median_cycle_time": round(median, 2),
            "max_cycle_time": round(Q3, 2),
            "variance": round(variance, 2)
        })

    return pd.DataFrame(results)

def date_calculation(date):
    start = (date).replace(hour=8, minute=0, second=0, microsecond=0)
    mid = (date).replace(hour=20, minute=0, second=0, microsecond=0)
    end = (date + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return start, mid, end


yesterday_date_8am = (datetime.now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
yesterday_date_8pm = (datetime.now() - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
current_date_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

STOP_ACTIONS = {"abnormal_cycle", "downtime"}
PRODUCTION_ACTIONS = ("normal_cycle", "abnormal_cycle", "downtime")
MANUAL_STOP_BOUNDARY_ACTIONS = {"change mould start", "adjustment start"}

# Firmware in ESP_LOG_TXT_WITH_TASK_IMPROVED stops logging when downtime exceeds
# this threshold; orphan clusters can never realistically exceed it.
MAX_OPEN_CLUSTER_HOURS = 5


def _shift_name(timestamp_value):
    return "Shift 1" if 8 <= timestamp_value.hour < 20 else "Shift 2"


def _empty_stop_clusters():
    return pd.DataFrame(
        columns=[
            "mp_id",
            "machine_code",
            "mould_id",
            "start_id",
            "end_id",
            "start_action",
            "closed_by",
            "cluster_start_time",
            "cluster_end_time",
            "duration_seconds",
            "duration_hr",
            "hour",
            "shift",
        ]
    )


def _build_shift_hour_frame(cluster_df, shift_name):
    hours = list(range(8, 20)) if shift_name == "Shift 1" else list(range(20, 24)) + list(range(0, 8))
    base = pd.DataFrame({"hour": hours})

    if cluster_df is None or cluster_df.empty:
        base["stops"] = 0
        base["shift"] = shift_name
        return base

    grouped = (
        cluster_df[cluster_df["shift"] == shift_name]
        .groupby("hour")
        .size()
        .reset_index(name="stops")
    )

    merged = base.merge(grouped, on="hour", how="left").fillna(0).infer_objects(copy=False)
    merged["stops"] = merged["stops"].astype(int)
    merged["shift"] = shift_name
    return merged


def _build_stop_clusters(events_df, window_end, manual_events_df=None):
    if (events_df is None or events_df.empty) and (manual_events_df is None or manual_events_df.empty):
        return _empty_stop_clusters()

    production_events = (
        events_df.copy()
        if events_df is not None
        else pd.DataFrame(
            columns=[
                "idmonitoring",
                "mp_id",
                "action",
                "time_input",
                "machine_code",
                "mould_id",
            ]
        )
    )
    manual_events = (
        manual_events_df.copy()
        if manual_events_df is not None
        else pd.DataFrame(columns=["idmonitoring", "action", "time_input", "machine_code", "mould_id"])
    )

    if production_events.empty and manual_events.empty:
        return _empty_stop_clusters()

    if not production_events.empty:
        production_events["time_input"] = pd.to_datetime(production_events["time_input"])
        production_events["event_source"] = "production"
        production_events["event_priority"] = 1

    if not manual_events.empty:
        manual_events["time_input"] = pd.to_datetime(manual_events["time_input"])
        manual_events["event_source"] = "manual"
        manual_events["event_priority"] = 0
        if "mp_id" not in manual_events.columns:
            manual_events["mp_id"] = pd.NA

    stream_columns = [
        "idmonitoring",
        "mp_id",
        "action",
        "time_input",
        "time_taken",
        "machine_code",
        "mould_id",
        "event_source",
        "event_priority",
    ]
    event_stream = pd.concat(
        [
            production_events.reindex(columns=stream_columns),
            manual_events.reindex(columns=stream_columns),
        ],
        ignore_index=True,
    )
    event_stream = event_stream.dropna(subset=["machine_code", "time_input"])
    event_stream = event_stream.sort_values(
        ["machine_code", "time_input", "event_priority", "idmonitoring"]
    ).reset_index(drop=True)

    clusters = []
    window_end_ts = pd.Timestamp(window_end)
    window_start_ts = window_end_ts - pd.Timedelta(days=1)

    for machine_code, group in event_stream.groupby("machine_code", sort=False):
        open_cluster = None

        for row in group.itertuples(index=False):
            action = row.action
            event_time = pd.Timestamp(row.time_input)
            time_taken_seconds = (
                float(row.time_taken)
                if pd.notna(getattr(row, "time_taken", None))
                else 0.0
            )

            if action == "abnormal_cycle":
                # Auto -> manual transition; opens a stop interval that a later
                # `downtime` (or boundary/normal) event will close.
                if open_cluster is None:
                    open_cluster = {
                        "mp_id": getattr(row, "mp_id", None),
                        "machine_code": machine_code,
                        "mould_id": getattr(row, "mould_id", None),
                        "start_id": getattr(row, "idmonitoring", None),
                        "start_action": action,
                        "cluster_start_time": event_time,
                    }
                continue

            if action == "downtime":
                # Firmware publishes `downtime` when auto-mode resumes; its
                # time_taken is the duration of the just-ended stop period.
                period_start = event_time - pd.Timedelta(seconds=time_taken_seconds)
                period_start = max(period_start, window_start_ts)

                if open_cluster is not None:
                    cluster_start = min(
                        open_cluster["cluster_start_time"], period_start
                    )
                    open_cluster["cluster_start_time"] = cluster_start
                    open_cluster["cluster_end_time"] = event_time
                    open_cluster["end_id"] = getattr(row, "idmonitoring", None)
                    open_cluster["closed_by"] = "downtime"
                    clusters.append(open_cluster)
                    open_cluster = None
                elif event_time > period_start:
                    clusters.append(
                        {
                            "mp_id": getattr(row, "mp_id", None),
                            "machine_code": machine_code,
                            "mould_id": getattr(row, "mould_id", None),
                            "start_id": getattr(row, "idmonitoring", None),
                            "start_action": "downtime",
                            "cluster_start_time": period_start,
                            "cluster_end_time": event_time,
                            "end_id": getattr(row, "idmonitoring", None),
                            "closed_by": "downtime",
                        }
                    )
                continue

            if (
                action == "normal_cycle" or action in MANUAL_STOP_BOUNDARY_ACTIONS
            ) and open_cluster is not None:
                open_cluster["cluster_end_time"] = event_time
                open_cluster["end_id"] = getattr(row, "idmonitoring", None)
                open_cluster["closed_by"] = action
                clusters.append(open_cluster)
                open_cluster = None

        if open_cluster is not None:
            cap = open_cluster["cluster_start_time"] + pd.Timedelta(
                hours=MAX_OPEN_CLUSTER_HOURS
            )
            cap = min(cap, window_end_ts)
            open_cluster["cluster_end_time"] = cap
            open_cluster["end_id"] = None
            open_cluster["closed_by"] = (
                "firmware_5h_cap" if cap < window_end_ts else "window_end"
            )
            clusters.append(open_cluster)

    cluster_df = pd.DataFrame(
        clusters,
        columns=[
            "mp_id",
            "machine_code",
            "mould_id",
            "start_id",
            "end_id",
            "start_action",
            "closed_by",
            "cluster_start_time",
            "cluster_end_time",
        ],
    )

    if cluster_df.empty:
        return _empty_stop_clusters()

    cluster_df["cluster_start_time"] = pd.to_datetime(cluster_df["cluster_start_time"])
    cluster_df["cluster_end_time"] = pd.to_datetime(cluster_df["cluster_end_time"])
    cluster_df["duration_seconds"] = (
        cluster_df["cluster_end_time"] - cluster_df["cluster_start_time"]
    ).dt.total_seconds().clip(lower=0)
    cluster_df["duration_hr"] = cluster_df["duration_seconds"] / 3600
    cluster_df["hour"] = cluster_df["cluster_start_time"].dt.hour
    cluster_df["shift"] = cluster_df["cluster_start_time"].apply(_shift_name)
    return cluster_df


def _fetch_production_events(start_time, end_time, mp_id=None, machine_code=None):
    query = """
    SELECT
        monitoring.idmonitoring,
        monitoring.main_id,
        monitoring.mp_id,
        monitoring.action,
        monitoring.time_taken,
        monitoring.time_input,
        production.mould_id,
        production.machine_code,
        ml.standard_ct
    FROM machine_monitoring.monitoring AS monitoring
    INNER JOIN machine_monitoring.mass_production AS production
        ON monitoring.mp_id = production.mp_id
    INNER JOIN machine_monitoring.mould_list AS ml
        ON production.mould_id = ml.mould_code
    WHERE monitoring.time_input BETWEEN :start_time AND :end_time
      AND monitoring.action IN ('normal_cycle', 'abnormal_cycle', 'downtime')
    """

    params = {
        "start_time": start_time,
        "end_time": end_time,
    }

    if mp_id is not None:
        query += " AND monitoring.mp_id = :mp_id"
        params["mp_id"] = mp_id

    if machine_code is not None:
        query += " AND production.machine_code = :machine_code"
        params["machine_code"] = machine_code

    query += " ORDER BY monitoring.mp_id, monitoring.time_input, monitoring.idmonitoring"

    with get_db_engine().connect() as connection:
        df = pd.read_sql(text(query), connection, params=params)

    if df.empty:
        return df

    df = df.drop_duplicates(subset=["idmonitoring"]).reset_index(drop=True)
    df["time_input"] = pd.to_datetime(df["time_input"])
    df["date"] = df["time_input"].dt.date
    return df


def _fetch_manual_boundary_events(start_time, end_time, machine_code=None):
    query = """
    SELECT
        monitoring.idmonitoring,
        monitoring.main_id,
        monitoring.action,
        monitoring.time_input,
        joblist.machine_code,
        joblist.mould_code AS mould_id
    FROM machine_monitoring.monitoring AS monitoring
    INNER JOIN machine_monitoring.joblist AS joblist
        ON monitoring.main_id = joblist.main_id
    WHERE monitoring.time_input BETWEEN :start_time AND :end_time
      AND monitoring.action IN ('adjustment start', 'change mould start')
    """

    params = {
        "start_time": start_time,
        "end_time": end_time,
    }

    if machine_code is not None:
        query += " AND joblist.machine_code = :machine_code"
        params["machine_code"] = machine_code

    query += " ORDER BY joblist.machine_code, monitoring.time_input, monitoring.idmonitoring"

    with get_db_engine().connect() as connection:
        df = pd.read_sql(text(query), connection, params=params)

    if df.empty:
        return df

    df = df.drop_duplicates(subset=["idmonitoring"]).reset_index(drop=True)
    df["time_input"] = pd.to_datetime(df["time_input"])
    return df


def fetch_data(start_time ,mid_time , end_time ):
    return _fetch_production_events(start_time, end_time)

def daily_report(date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    start_time, mid_time, end_time = date_calculation(date)
    event_df = fetch_data(start_time, mid_time, end_time)

    if event_df.empty:
        return (
            pd.DataFrame(columns=[
                "mp_id", "machine_code", "mould_id", "total_stops",
                "shift_1_stops", "shift_1_downtime",
                "shift_2_stops", "shift_2_downtime", "standard_ct",
            ]),
            {"shift_1_totaldt": 0, "shift_2_totaldt": 0, "overall_totaldt": 0}
        )

    information_df = fetch_data_variation(date)

    if not information_df.empty:
        information_df = calculate_filtered_variance_by_group(information_df, "mp_id", "time_taken")
    else:
        information_df = pd.DataFrame(
            columns=["mp_id", "min_cycle_time", "median_cycle_time", "max_cycle_time", "variance"]
        )

    df_unique = event_df[["mp_id", "machine_code", "mould_id", "standard_ct"]].drop_duplicates(subset="mp_id")

    manual_boundary_df = _fetch_manual_boundary_events(start_time, end_time)
    cluster_df = _build_stop_clusters(event_df, end_time, manual_boundary_df)
    if cluster_df.empty:
        df_stop_counts = pd.DataFrame(columns=["mp_id", "shift_1_stops", "shift_2_stops"])
    else:
        df_stop_counts = (
            cluster_df.assign(stop_count=1)
            .pivot_table(index="mp_id", columns="shift", values="stop_count", aggfunc="sum", fill_value=0)
            .reset_index()
            .rename(columns={"Shift 1": "shift_1_stops", "Shift 2": "shift_2_stops"})
        )

    for column in ["shift_1_stops", "shift_2_stops"]:
        if column not in df_stop_counts.columns:
            df_stop_counts[column] = 0

    if cluster_df.empty:
        df_downtime = pd.DataFrame(columns=["mp_id", "shift_1_downtime", "shift_2_downtime"])
    else:
        df_downtime = (
            cluster_df
            .pivot_table(index="mp_id", columns="shift", values="duration_seconds", aggfunc="sum", fill_value=0)
            .reset_index()
            .rename(columns={"Shift 1": "shift_1_downtime", "Shift 2": "shift_2_downtime"})
        )

    for column in ["shift_1_downtime", "shift_2_downtime"]:
        if column not in df_downtime.columns:
            df_downtime[column] = 0

    merged = pd.merge(df_unique, df_stop_counts, how="left", on="mp_id")
    merged = pd.merge(merged, df_downtime, how="left", on="mp_id")
    merged = pd.merge(merged, information_df, how="left", on="mp_id", suffixes=("", "_info"))

    merged.fillna({
        "shift_1_stops": 0,
        "shift_1_downtime": 0,
        "shift_2_stops": 0,
        "shift_2_downtime": 0
    }, inplace=True)
    merged = merged.infer_objects(copy=False)

    # Calculate total_stops
    merged['total_stops'] = merged['shift_1_stops'] + merged['shift_2_stops']

    # Add downtime in minutes columns
    merged['shift_1_downtime_minutes'] = (merged['shift_1_downtime'] / 60).round(2)
    merged['shift_2_downtime_minutes'] = (merged['shift_2_downtime'] / 60).round(2)

    shift1_totaldt = merged["shift_1_downtime_minutes"].sum()
    shift2_totaldt = merged["shift_2_downtime_minutes"].sum()
    overall_totaldt = shift1_totaldt + shift2_totaldt

    # Reorder columns to place 'total_stops' after 'mould_id'
    cols = list(merged.columns)
    if 'total_stops' in cols and 'mould_id' in cols:
        cols.remove('total_stops')
        mould_index = cols.index('mould_id')
        cols.insert(mould_index + 1, 'total_stops')
        merged = merged[cols]
    merged = merged.sort_values(by="total_stops", ascending=False).reset_index(drop=True)

    return merged, {"shift_1_totaldt": shift1_totaldt, "shift_2_totaldt": shift2_totaldt, "overall_totaldt": overall_totaldt}


# def hourly(mp_id=None, date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
#     if isinstance(date, str):
#         date = datetime.strptime(date, "%Y-%m-%d")
    
#     start, _, end = date_calculation(date)
    
#     if mp_id:
#         df, _ = calculate_downtime(mp_id)
#         df["time_input"] = pd.to_datetime(df["time_input"])

#         # Filter to the defined date range
#         df = df[(df["time_input"] >= start) & (df["time_input"] < end)]


#         df2 = df[df["action"] == "abnormal_cycle"].copy()
#         # Only keep rows with action == "downtime"
#         df = df[df["action"] == "downtime"].copy()

        
#         print(df2)
#         # Assign hour and shift
#         df["hour"] = df["time_input"].dt.hour
#         df["shift"] = df["time_input"].apply(
#             lambda x: "Shift 1" if 8 <= x.hour < 20 else "Shift 2"
#         )

#         # Group by shift and hour
#         grouped = df.groupby(["shift", "hour"]).size().reset_index(name="stops")

#         # Fill in all hours for Shift 1 (8–19) and Shift 2 (20–23 and 0–7)
#         shift1_hours = pd.DataFrame({"hour": range(8, 20)})
#         shift2_hours = pd.DataFrame({"hour": list(range(20, 24)) + list(range(0, 8))})

#         shift1 = shift1_hours.merge(
#             grouped[grouped["shift"] == "Shift 1"], on="hour", how="left"
#         ).fillna(0).infer_objects(copy=False)
#         shift1["stops"] = shift1["stops"].astype(int)
#         shift1["shift"] = "Shift 1"

#         shift2 = shift2_hours.merge(
#             grouped[grouped["shift"] == "Shift 2"], on="hour", how="left"
#         ).fillna(0).infer_objects(copy=False)
#         shift2["stops"] = shift2["stops"].astype(int)
#         shift2["shift"] = "Shift 2"

#         return shift1, shift2
#     else:
#         print("No MP ID provided.")
#         return pd.DataFrame(), pd.DataFrame()

def hourly(mp_id=None, date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")

    report_date = date.date() if isinstance(date, datetime) else date
    start_time, _mid_time, end_time = date_calculation_new(report_date)

    if not mp_id:
        print("No MP ID provided.")
        return pd.DataFrame(), pd.DataFrame()

    event_df = _fetch_production_events(start_time, end_time, mp_id=mp_id)
    if event_df is None or event_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    machine_code = event_df["machine_code"].iloc[0]
    machine_events_df = _fetch_production_events(start_time, end_time, machine_code=machine_code)
    manual_boundary_df = _fetch_manual_boundary_events(start_time, end_time, machine_code=machine_code)
    cluster_df = _build_stop_clusters(machine_events_df, end_time, manual_boundary_df)
    cluster_df = cluster_df[cluster_df["mp_id"] == mp_id].copy()

    shift1 = _build_shift_hour_frame(cluster_df, "Shift 1")
    shift2 = _build_shift_hour_frame(cluster_df, "Shift 2")

    return shift1, shift2

# print(hourly(449, "2025-09-24"))

def date_calculation_new(date):
    # Ensure date is a datetime.date object
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    # Convert date to datetime for time replacement
    date = datetime.combine(date, datetime.min.time())

    start = (date).replace(hour=8, minute=0, second=0, microsecond=0)
    mid   = (date).replace(hour=20, minute=0, second=0, microsecond=0)
    end   = (date + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)

    return start, mid, end


def calculate_downtime_daily_report(mp_id, date=datetime.now().date()):
    if not mp_id:  # Check if mp_id is None or empty
        print("Error: mp_id is None or empty")
        return pd.DataFrame(), None  # Return an empty DataFrame to prevent errors
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()
    start_date, _mid_time, end_date = date_calculation_new(date)

    df = _fetch_production_events(start_date, end_date, mp_id=mp_id)

    if df.empty:
        print("No data found for the given mp_id and date.")
        return pd.DataFrame(), {
            "production_time": 0,
            "ideal_time": 0,
            "downtime": 0,
            "efficiency": 0,
            "total_times_stoped": 0,
            "median_cycle_time": 0,
            "total_shots": 0,
            "start_time": start_date,
            "end_time": end_date,
        }

    df = df.copy()
    action_totals = df.groupby("action")["time_taken"].sum()
    machine_code = df["machine_code"].iloc[0]
    machine_events_df = _fetch_production_events(start_date, end_date, machine_code=machine_code)
    manual_boundary_df = _fetch_manual_boundary_events(start_date, end_date, machine_code=machine_code)
    cluster_df = _build_stop_clusters(machine_events_df, end_date, manual_boundary_df)
    cluster_df = cluster_df[cluster_df["mp_id"] == mp_id].copy()
    start_time = df["time_input"].min()
    end_time = df["time_input"].max()

    total_stop = len(cluster_df.index)
    total_shots = len(df[df["action"] == "normal_cycle"])
    normal_cycle_seconds = float(action_totals.get("normal_cycle", 0))
    downtime_seconds = float(cluster_df["duration_seconds"].sum()) if not cluster_df.empty else 0.0
    total_running = normal_cycle_seconds + downtime_seconds
    median_cycle_time = round(df["time_taken"].median(), 2)

    cycle_time = float(df["standard_ct"].iloc[0]) if not df["standard_ct"].isna().all() else 0
    ideal_time = total_shots * cycle_time
    downtime = downtime_seconds

    efficiency = ((total_shots * cycle_time) / total_running) * 100 if total_running else 0

    if cluster_df.empty:
        filtered_df = pd.DataFrame(
            columns=[
                "start_id",
                "end_id",
                "time_input",
                "end_time",
                "time_taken",
                "total_minutes",
                "closed_by",
            ]
        )
    else:
        filtered_df = cluster_df.sort_values(by="cluster_start_time").reset_index(drop=True)
        filtered_df["time_input"] = filtered_df["cluster_start_time"]
        filtered_df["end_time"] = filtered_df["cluster_end_time"]
        filtered_df["time_taken"] = filtered_df["duration_seconds"].round(1)
        filtered_df["total_minutes"] = (filtered_df["duration_seconds"] / 60).round(2)
        filtered_df = filtered_df[
            [
                "start_id",
                "end_id",
                "time_input",
                "end_time",
                "time_taken",
                "total_minutes",
                "closed_by",
            ]
        ]

    return filtered_df, {
        "production_time": total_running,
        "ideal_time": ideal_time,
        "downtime": downtime,
        "efficiency": efficiency,
        "total_times_stoped": total_stop,
        "median_cycle_time": median_cycle_time,
        "total_shots": total_shots,
        "start_time": start_time,
        "end_time": end_time,
    }



def previous_month_dates(date=datetime.now()):
    # Get the current date
    # today = datetime.now()
    # Calculate the first day of the current month
    first_day_current_month = date.replace(day=1)
    # Subtract one day to get the last day of the previous month
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    # Replace the day to 1 to get the first day of the previous month
    first_day_previous_month = last_day_previous_month.replace(day=1)
    return first_day_previous_month, last_day_previous_month


"""

so query all the data from monitoring

"""


def fetch_data_monthly(machine_selected, date= datetime.now()):

    start_time, end_time = previous_month_dates(date)

    query = text("""
        SELECT monitoring.*, production.mould_id, production.machine_code
        FROM machine_monitoring.monitoring AS monitoring
        INNER JOIN machine_monitoring.mass_production AS production
            ON monitoring.mp_id = production.mp_id
        WHERE monitoring.time_input BETWEEN :start_time AND :end_time
        AND monitoring.action IN ('downtime');
    """)

    query2 = text("""
        SELECT monitoring.*, production.mould_id, production.machine_code
        FROM machine_monitoring.monitoring AS monitoring
        INNER JOIN machine_monitoring.mass_production AS production
            ON monitoring.mp_id = production.mp_id
        WHERE monitoring.time_input BETWEEN :start_time AND :end_time
        AND monitoring.action IN ('normal_cycle');
    """)

    # Run query and load into a DataFrame
    with get_db_engine().connect() as connection:

        df_unique = pd.read_sql(query2, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })

        # Get unique machine_code and corresponding mould_id
        machines_running = df_unique.groupby([ "machine_code"])["mould_id"].first().reset_index()
        # print(machines_running)

        # Convert to DataFrame
        df_main = pd.DataFrame(machines_running)
        # print(df_main)

        df = pd.read_sql(query, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })

        df['time_input'] = pd.to_datetime(df['time_input'])
        df["day"] = df["time_input"].dt.date

        # print(df)
            # Aggregate data for Shift 1
        df_overall = df_detailed = df.groupby(["machine_code"]).agg(
            month_total_stop=("idmonitoring", "count"),
            month_total_dt=("time_taken", "sum")
        ).reset_index()  



        df_detailed = df.groupby(["machine_code", "mould_id"]).agg(
            month_total_stop=("idmonitoring", "count"),
            month_total_dt=("time_taken", "sum")
        ).reset_index()    

        df_detailed["stop_percentage"] = (
        df_detailed["month_total_stop"] / 
        df_detailed.groupby("machine_code")["month_total_stop"].transform("sum")
    ) * 100
        df_detailed["stop_percentage"] = df_detailed["stop_percentage"].round(2)
        filtered_df_detailed = df_detailed[df_detailed['machine_code'] == machine_selected]
        # filtered_df_overall = df_overall[df_detailed['machine_code'] == machine_selected]




    return df_overall, filtered_df_detailed


def monthly(machine_code=None, date=datetime.now()):

    if machine_code == None:
        # print("No machine code provided.")
        return go.Figure()
    else:
        start_time, end_time = previous_month_dates(date)

        query = text("""
            SELECT monitoring.*, production.mould_id, production.machine_code
            FROM machine_monitoring.monitoring AS monitoring
            INNER JOIN machine_monitoring.mass_production AS production
                ON monitoring.mp_id = production.mp_id
            WHERE monitoring.time_input BETWEEN :start_time AND :end_time
            AND monitoring.action IN ('downtime')
            AND production.machine_code IN (:machine_code);
        """)

        # Run query and load into a DataFrame
        with get_db_engine().connect() as connection:
            df_filtered = pd.read_sql(query, connection, params={
                "start_time": start_time,
                "end_time": end_time,
                "machine_code": machine_code
            })

        # print(df_filtered)
        df_filtered['time_input'] = pd.to_datetime(df_filtered['time_input'])
        df_filtered["day"] = df_filtered["time_input"].dt.date

        month_range = pd.DataFrame({
            "day": pd.date_range(start=start_time, end=end_time)
        })

        # Convert to date only (no time part)
        month_range["day"] = month_range["day"].dt.date

        grouped = df_filtered.groupby(["day"]).size().reset_index(name="stops")

        # Convert 'day' in grouped to date only
        grouped["day"] = pd.to_datetime(grouped["day"]).dt.date

        # Merge
        daily = month_range.merge(grouped, on="day", how="left").fillna(0)
        daily["stops"] = daily["stops"].astype(int)

        return daily

def get_main_id (mp_id):

    query = text (f"""SELECT main_id FROM machine_monitoring.monitoring
                where mp_id = :mp_id
                limit 1 """)
    
    with get_db_engine().connect() as connection:
        df_filtered = pd.read_sql(query, connection, params={
            "mp_id": mp_id,
        })

    main_id = df_filtered["main_id"].loc[0]

    query = text("""SELECT action, time_taken, time_input FROM machine_monitoring.monitoring
                where main_id = :main_id
                limit 2""")
    
    with get_db_engine().connect() as connection:
        df_change_mould_info = pd.read_sql(query, connection, params={
            "main_id": main_id,
        })
    df_dict = df_change_mould_info.to_dict(orient='records')

    return df_dict






def mould_activities (date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    window_start, _, window_end = date_calculation(date)

    query = text("""
    SELECT 
        monitoring.idmonitoring,
        machine_code, 
        joblist.mould_code,
        part_name,
        monitoring.action, 
        monitoring.main_id,
        monitoring.time_taken,
        monitoring.time_input, 
        monitoring.remarks
        
    FROM 
        machine_monitoring.monitoring
    INNER JOIN 
        machine_monitoring.joblist 
        ON monitoring.main_id = joblist.main_id
    INNER JOIN
        machine_monitoring.mould_list 
        ON joblist.mould_code = mould_list.mould_code
    WHERE 
        monitoring.action IN ('adjustment start', 'adjustment end', 'change mould start', 'change mould end')
        AND monitoring.time_input BETWEEN :start_time AND :end_time;

    """)

    with get_db_engine().connect() as connection:

        df = pd.read_sql(query, connection, params={
            "start_time": window_start,
            "end_time": window_end
        })

    activity_columns = [
        'machine_code',
        'mould_code',
        'part_name',
        'main_id',
        'base_action',
        'start_time',
        'end_time',
        'duration_hr',
        'remarks',
    ]

    if df.empty:
        return pd.DataFrame(columns=activity_columns), 0.0, 0.0

    # Convert to datetime
    df = df.drop_duplicates(subset=['idmonitoring']).copy()
    df['time_input'] = pd.to_datetime(df['time_input'])

    # Normalize action
    df['base_action'] = df['action'].str.replace(r' (start|end)$', '', regex=True)
    df = df.sort_values(['main_id', 'base_action', 'time_input', 'idmonitoring'])

    paired_rows = []

    for (_, _), group in df.groupby(['main_id', 'base_action'], sort=False):
        open_starts = []

        for row in group.itertuples(index=False):
            if row.action.endswith('start'):
                open_starts.append(row)
                continue

            if not row.action.endswith('end'):
                continue

            duration_seconds = float(row.time_taken) if pd.notna(row.time_taken) and row.time_taken > 0 else None

            if open_starts:
                start_row = open_starts.pop(0)
                activity_start = start_row.time_input
                machine_code = start_row.machine_code
                mould_code = start_row.mould_code
                part_name = start_row.part_name if pd.notna(start_row.part_name) else row.part_name
            elif duration_seconds is not None:
                activity_start = row.time_input - timedelta(seconds=duration_seconds)
                machine_code = row.machine_code
                mould_code = row.mould_code
                part_name = row.part_name
            else:
                continue

            if duration_seconds is None:
                duration_seconds = max((row.time_input - activity_start).total_seconds(), 0.0)

            activity_end = row.time_input
            clipped_start = max(activity_start, window_start)
            clipped_end = min(activity_end, window_end)

            if clipped_end <= clipped_start:
                continue

            paired_rows.append(
                {
                    'machine_code': machine_code,
                    'mould_code': mould_code,
                    'part_name': part_name,
                    'main_id': row.main_id,
                    'base_action': row.base_action,
                    'start_time': clipped_start,
                    'end_time': clipped_end,
                    'duration_hr': round((clipped_end - clipped_start).total_seconds() / 3600, 2),
                    'remarks': row.remarks,
                }
            )

        for start_row in open_starts:
            clipped_start = max(start_row.time_input, window_start)
            clipped_end = window_end

            if clipped_end <= clipped_start:
                continue

            paired_rows.append(
                {
                    'machine_code': start_row.machine_code,
                    'mould_code': start_row.mould_code,
                    'part_name': start_row.part_name,
                    'main_id': start_row.main_id,
                    'base_action': start_row.base_action,
                    'start_time': clipped_start,
                    'end_time': clipped_end,
                    'duration_hr': round((clipped_end - clipped_start).total_seconds() / 3600, 2),
                    'remarks': start_row.remarks,
                }
            )

    if not paired_rows:
        return pd.DataFrame(columns=activity_columns), 0.0, 0.0

    merged = pd.DataFrame(paired_rows, columns=activity_columns)

    # Totals
    change_mould_total = merged[merged['base_action'] == 'change mould']['duration_hr'].sum()
    adjustment_total = merged[merged['base_action'] == 'adjustment']['duration_hr'].sum()

    return (
        merged[['machine_code', 'mould_code', 'part_name', 'main_id', 'base_action', 'start_time', 'end_time', 'duration_hr', 'remarks']],
        change_mould_total,
        adjustment_total
    )



def efficiency_sql_only(date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start_time, _, end_time = date_calculation(date)
    query = text("""
        SELECT
            activity.machine_code,
            SUM(activity.time_taken) / 3600 AS total_time_taken,
            SUM(CASE WHEN activity.action = 'normal_cycle' THEN activity.time_taken ELSE 0 END) / 3600 AS normal_cycle_time,
            SUM(CASE WHEN activity.action = 'abnormal_cycle' THEN activity.time_taken ELSE 0 END) / 3600 AS abnormal_cycle_time,
            SUM(CASE WHEN activity.action = 'downtime' THEN activity.time_taken ELSE 0 END) / 3600 AS downtime_time,
            SUM(CASE WHEN activity.action = 'normal_cycle' THEN 1 ELSE 0 END) AS shot_count,
            MIN(activity.time_input) AS first_input_time,
            MAX(activity.time_input) AS last_input_time,
            TIMEDIFF(MAX(activity.time_input), MIN(activity.time_input)) AS total_running_time,
            ROUND(
                COALESCE(
                    SUM(CASE WHEN activity.action = 'normal_cycle' THEN activity.time_taken ELSE 0 END)
                    / NULLIF(SUM(activity.time_taken), 0) * 100,
                    0
                ),
                2
            ) AS efficiency_percent
        FROM (
            SELECT
                COALESCE(mp.machine_code, j.machine_code) AS machine_code,
                monitoring.action,
                monitoring.time_taken,
                monitoring.time_input
            FROM monitoring
            LEFT JOIN mass_production AS mp ON monitoring.mp_id = mp.mp_id
            LEFT JOIN joblist AS j ON monitoring.main_id = j.main_id
            WHERE monitoring.time_input BETWEEN :start_time AND :end_time
              AND monitoring.action IN ('normal_cycle', 'abnormal_cycle', 'downtime')
        ) AS activity
        WHERE activity.machine_code IS NOT NULL
        GROUP BY activity.machine_code;
        """)

        # Run query and load into a DataFrame
    with get_db_engine().connect() as connection:
        df = pd.read_sql(query, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })

    if df.empty:
        return df

    # Convert to timedelta
    df['total_running_time'] = pd.to_timedelta(df['total_running_time'])

    # Keep the legacy 24-hour gap view used by the productivity table.
    df['downtime'] = 24 - df['normal_cycle_time']
    df['efficiency'] = df['efficiency_percent'].round(2)

    # Drop if not needed later
    return df.drop(columns=['total_running_time'])



def combined_output(date, actions_result=None):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")

    start_time, _, end_time = date_calculation(date)
    production_df = _fetch_production_events(start_time, end_time)
    if actions_result is None:
        df_actions, x, y = mould_activities(date)
    else:
        df_actions, x, y = actions_result

    if production_df is None or production_df.empty:
        return production_df, 0.0, 0.0, 0.0

    manual_boundary_df = _fetch_manual_boundary_events(start_time, end_time)
    cluster_df = _build_stop_clusters(production_df, end_time, manual_boundary_df)

    df_summary = (
        production_df.assign(
            normal_cycle_seconds=production_df["time_taken"].where(
                production_df["action"] == "normal_cycle", 0.0
            ),
            abnormal_cycle_seconds=production_df["time_taken"].where(
                production_df["action"] == "abnormal_cycle", 0.0
            ),
        )
        .groupby("machine_code", as_index=False)
        .agg(
            normal_cycle_time=("normal_cycle_seconds", lambda s: round(float(s.sum()) / 3600, 2)),
            abnormal_cycle_time=("abnormal_cycle_seconds", lambda s: round(float(s.sum()) / 3600, 2)),
            shot_count=("action", lambda s: int((s == "normal_cycle").sum())),
            first_input_time=("time_input", "min"),
            last_input_time=("time_input", "max"),
        )
    )

    if cluster_df.empty:
        downtime_df = pd.DataFrame(columns=["machine_code", "downtime"])
    else:
        downtime_df = (
            cluster_df
            .groupby("machine_code", as_index=False)["duration_hr"]
            .sum()
            .rename(columns={"duration_hr": "downtime"})
        )

    df_summary = df_summary.merge(downtime_df, on="machine_code", how="left")
    df_summary["downtime"] = df_summary["downtime"].fillna(0).round(2)
    df_actions = df_actions.copy()

    pivot_actions = df_actions.pivot_table(
        index='machine_code',
        columns='base_action',
        values='duration_hr',
        aggfunc='sum'
    ).reset_index()

    pivot_actions.columns.name = None
    pivot_actions = pivot_actions.rename(columns={
        'change mould': 'total_change_mould_hr',
        'adjustment': 'total_adjustment_hr'
    })

    for col in ['total_change_mould_hr', 'total_adjustment_hr']:
        if col not in pivot_actions.columns:
            pivot_actions[col] = 0

    df_merged = df_summary.merge(pivot_actions, on='machine_code', how='left')

    df_merged[['total_change_mould_hr', 'total_adjustment_hr']] = df_merged[
        ['total_change_mould_hr', 'total_adjustment_hr']].fillna(0)

    df_merged['total_time_taken'] = (
        df_merged['normal_cycle_time']
        + df_merged['downtime']
        + df_merged['total_adjustment_hr']
        + df_merged['total_change_mould_hr']
    ).clip(upper=24).round(2)

    df_merged['machine_capacity'] = (df_merged['normal_cycle_time'] / 24 * 100).round(2)
    df_merged['efficiency'] = (
        (df_merged['normal_cycle_time'] / df_merged['total_time_taken'].where(df_merged['total_time_taken'] > 0)) * 100
    ).fillna(0).round(2)

    actual_total_gain_hr = df_merged['normal_cycle_time'].sum()
    total_actual_avail_hr = df_merged['total_time_taken'].sum()
    running_machine_count = len(df_merged.index)
    planned_capacity_hours = running_machine_count * 24

    actual_productivity = float(round((actual_total_gain_hr / total_actual_avail_hr) * 100, 2)) if total_actual_avail_hr else 0.0
    planned_productivity = float(round((actual_total_gain_hr / planned_capacity_hours) * 100, 2)) if planned_capacity_hours else 0.0
    overall_efficiency = actual_productivity

    numeric_cols = [
        'total_time_taken',
        'normal_cycle_time',
        'abnormal_cycle_time',
        'downtime',
        'total_adjustment_hr',
        'total_change_mould_hr',
    ]

    df_merged.loc['Total', numeric_cols] = df_merged[numeric_cols].sum().round(2)

    df_merged.loc['Total', 'efficiency'] = overall_efficiency
    df_merged.loc['Total', 'shot_count'] = round(df_merged['shot_count'].sum(), 2) if not df_merged['shot_count'].empty else 0.0

    for col in ['machine_code', 'first_input_time', 'last_input_time']:
        df_merged[col] = df_merged[col].astype("object")
        df_merged.loc['Total', col] = ''

    desired_order = [
        'machine_code',
        'total_time_taken',
        'normal_cycle_time',
        'downtime',
        'total_adjustment_hr',
        'total_change_mould_hr',
        'shot_count',
        'first_input_time',
        'last_input_time',
        'efficiency',
        # 'efficiency_percent',
        # 'machine_capacity'
    ]
    df_merged = df_merged.reindex(columns=desired_order)
    
    return df_merged, actual_productivity, planned_productivity, overall_efficiency
    




# df, x, y = get_mould_activities("2025-07-02")
# print(df, x,y)
# print(combined_output("2025-08-25"))
# print(mould_activities("2025-08-20"))
# print(efficiency_sql_only("2025-09-03"))
# date = "2025-09-05"
# date = datetime.strptime(date, "%Y-%m-%d")
# print(daily_report(date))

# start_time, mid_time, end_time = date_calculation(date)
# df_unique_raw, shift1, shift2 = fetch_data(start_time, mid_time, end_time)

# print(df_unique_raw, shift1, shift2)
