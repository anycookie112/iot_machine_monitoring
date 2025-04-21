from datetime import datetime, timedelta
from sqlalchemy import create_engine,text
import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config import DB_CONFIG
from utils.efficiency import calculate_downtime

db_connection_str = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

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

    # yesterday_date_8am = (datetime.now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    # yesterday_date_8pm = (datetime.now() - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    # current_date_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

    # Run query and load into a DataFrame
    with db_connection_str.connect() as connection:

        df = pd.read_sql(query, connection, params={
            "start_time": start,
            "end_time": mid
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

        results.append({
            group_col: group_val,
            f"max_cycle_time": Q1,
            "median_cycle_time": median,
            f"min_cycle_time": Q3,
            f"variance": variance
        })

    return pd.DataFrame(results)

def date_calculation(date):
    start = (date - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    mid = (date - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    end = date.replace(hour=8, minute=0, second=0, microsecond=0)
    return start, mid, end


yesterday_date_8am = (datetime.now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
yesterday_date_8pm = (datetime.now() - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
current_date_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)


def fetch_data(start_time ,mid_time , end_time ):
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
    with db_connection_str.connect() as connection:

        df_unique = pd.read_sql(query2, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })



        # Get unique machine_code and corresponding mould_id
        machines_running = df_unique.groupby(["mp_id", "machine_code"])["mould_id"].first().reset_index()
        # print(machines_running)

        # Convert to DataFrame
        df_main = pd.DataFrame(machines_running)
        # print(df_main)

        df = pd.read_sql(query, connection, params={
            "start_time": start_time,
            "end_time": mid_time
        })
        # print(df)

        df2 = pd.read_sql(query, connection, params={
            "start_time": mid_time,
            "end_time": end_time
        })

    df['time_input'] = pd.to_datetime(df['time_input'])
    df["date"] = df["time_input"].dt.date

    df2['time_input'] = pd.to_datetime(df2['time_input'])
    df2["date"] = df2["time_input"].dt.date

    # Optional cleanup
    data_excluded = df.drop(columns=['status', 'time_completed'], errors='ignore')
    return machines_running, df, df2

def daily_report(date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    start_time, mid_time, end_time = date_calculation(date)
    df_unique_raw, shift1, shift2 = fetch_data(start_time, mid_time, end_time)

    # If there's no data at all, return an empty DataFrame with the expected columns
    if shift1.empty and shift2.empty and df_unique_raw.empty:
        return pd.DataFrame(columns=[
            "mp_id", "machine_code", "mould_id", "total_stops",
            "shift_1_stops", "shift_1_downtime",
            "shift_2_stops", "shift_2_downtime",
            # add any other columns expected from information_df below
        ])

    information_df = fetch_data_variation(date)

    if not information_df.empty:
        information_df = calculate_filtered_variance_by_group(information_df, "mp_id", "time_taken")

    # Ensure df_unique has one row per mp_id
    df_unique = df_unique_raw[["mp_id", "machine_code", "mould_id"]].drop_duplicates(subset="mp_id")

    # Aggregate data for Shift 1
    df_counts1 = shift1.groupby("mp_id").agg(
        shift_1_stops=("idmonitoring", "count"),
        shift_1_downtime=("time_taken", "sum")
    ).reset_index()

    # Aggregate data for Shift 2
    df_counts2 = shift2.groupby("mp_id").agg(
        shift_2_stops=("idmonitoring", "count"),
        shift_2_downtime=("time_taken", "sum")
    ).reset_index()

    # Merge all together on mp_id
    merged = pd.merge(df_unique, df_counts1, how='outer', on='mp_id')
    merged = pd.merge(merged, df_counts2, how='outer', on='mp_id')
    merged = pd.merge(merged, information_df, how='outer', on='mp_id', suffixes=('', '_info'))


    # Optional: fill missing stop/downtime values with 0
    merged.fillna({
        "shift_1_stops": 0,
        "shift_1_downtime": 0,
        "shift_2_stops": 0,
        "shift_2_downtime": 0
    }, inplace=True)
    merged = merged.infer_objects(copy=False)

    # Calculate total_stops
    merged['total_stops'] = merged['shift_1_stops'] + merged['shift_2_stops']

    # Reorder columns to place 'total_stops' after 'mould_id'
    cols = list(merged.columns)
    if 'total_stops' in cols and 'mould_id' in cols:
        cols.remove('total_stops')
        mould_index = cols.index('mould_id')
        cols.insert(mould_index + 1, 'total_stops')
        merged = merged[cols]

    return merged

def hourly(mp_id=None, date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start, _, end = date_calculation(date)
    
    if mp_id:
        df, _ = calculate_downtime(mp_id)
        df["time_input"] = pd.to_datetime(df["time_input"])

        # Use today's date
        # today = datetime.today().date()

        # Define 24-hour window: yesterday 08:00 to today 08:00
        start = pd.to_datetime(f"{date - timedelta(days=1)} 08:00:00")
        end = pd.to_datetime(f"{date} 08:00:00")

        # Filter to the defined date range
        df = df[(df["time_input"] >= start) & (df["time_input"] < end)]

        # Only keep rows with action == "downtime"
        df = df[df["action"] == "downtime"].copy()

        # Assign hour and shift
        df["hour"] = df["time_input"].dt.hour
        df["shift"] = df["time_input"].apply(
            lambda x: "Shift 1" if 8 <= x.hour < 20 else "Shift 2"
        )

        # Group by shift and hour
        grouped = df.groupby(["shift", "hour"]).size().reset_index(name="stops")

        # Fill in all hours for Shift 1 (8–19) and Shift 2 (20–23 and 0–7)
        shift1_hours = pd.DataFrame({"hour": range(8, 20)})
        shift2_hours = pd.DataFrame({"hour": list(range(20, 24)) + list(range(0, 8))})

        shift1 = shift1_hours.merge(
            grouped[grouped["shift"] == "Shift 1"], on="hour", how="left"
        ).fillna(0)
        shift1["stops"] = shift1["stops"].astype(int)
        shift1["shift"] = "Shift 1"

        shift2 = shift2_hours.merge(
            grouped[grouped["shift"] == "Shift 2"], on="hour", how="left"
        ).fillna(0)
        shift2["stops"] = shift2["stops"].astype(int)
        shift2["shift"] = "Shift 2"

        return shift1, shift2
    else:
        print("No MP ID provided.")
        return pd.DataFrame(), pd.DataFrame()






# # # df, dummy = calculate_downtime(79)
# # # print(df)
parsed_date = datetime.strptime('2025-04-20', "%Y-%m-%d")

# # s1, s2 = hourly(73,parsed_date )
# # print("Shift 1:")
# # print(s1)
# # print("Shift 2:")
# # print(s2)
# # date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
# # start, _ , end = date_calculation(parsed_date)
# # x = fetch_data(start, _ , end)
# # print(x)

# y = daily_report(parsed_date)
# print(y)

df = daily_report(parsed_date)
print(df)

# df_unique_raw, shift1, shift2 = fetch_data()
# print(shift1)
# print(shift2)
# print(df2)
