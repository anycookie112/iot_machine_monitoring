from datetime import datetime, timedelta
from sqlalchemy import create_engine,text
import plotly.graph_objects as go
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

# def date_calculation(date):
#     start = (date - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
#     mid = (date - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
#     end = date.replace(hour=8, minute=0, second=0, microsecond=0)
#     return start, mid, end

def date_calculation(date):
    start = (date).replace(hour=8, minute=0, second=0, microsecond=0)
    mid = (date).replace(hour=20, minute=0, second=0, microsecond=0)
    end = (date + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
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

    # Add downtime in minutes columns
    merged['shift_1_downtime_minutes'] = (merged['shift_1_downtime'] / 60).round(2)
    merged['shift_2_downtime_minutes'] = (merged['shift_2_downtime'] / 60).round(2)

    shift1_totaldt = merged["shift_1_downtime_minutes"].sum()
    shift2_totaldt = merged["shift_2_downtime_minutes"].sum()
    overall_totaldt = shift1_totaldt + shift2_totaldt
    # print(f"Overall Total Downtime: {overall_totaldt} minutes")
    # print(f"Shift 1 Total Downtime: {shift1_totaldt} minutes")
    # print(f"Shift 2 Total Downtime: {shift2_totaldt} minutes")

    # Reorder columns to place 'total_stops' after 'mould_id'
    cols = list(merged.columns)
    if 'total_stops' in cols and 'mould_id' in cols:
        cols.remove('total_stops')
        mould_index = cols.index('mould_id')
        cols.insert(mould_index + 1, 'total_stops')
        merged = merged[cols]

    return merged, {"shift_1_totaldt": shift1_totaldt, "shift_2_totaldt": shift2_totaldt, "overall_totaldt": overall_totaldt}


def hourly(mp_id=None, date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start, _, end = date_calculation(date)
    
    if mp_id:
        df, _ = calculate_downtime(mp_id)
        df["time_input"] = pd.to_datetime(df["time_input"])

        # Define 24-hour window: yesterday 08:00 to today 08:00
        # start = pd.to_datetime(f"{date - timedelta(days=1)} 08:00:00")
        # end = pd.to_datetime(f"{date} 08:00:00")

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
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    db_engine = create_engine(db_connection_str)

    if not mp_id:  # Check if mp_id is None or empty
        print("Error: mp_id is None or empty")
        return pd.DataFrame(), None  # Return an empty DataFrame to prevent errors
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()
    # previous_date = date - timedelta(days=1)

    start_date, mid_time, end_date = date_calculation_new(date)

    # print(start_date, end_date)
 
    
    query = """
        SELECT DISTINCT m.*, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_list AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id = %s
        AND m.time_input BETWEEN %s AND %s
        ORDER BY m.time_input;
        """

    # Correctly define params as a tuple
    params = (mp_id,start_date, end_date,)

    # Execute query
    with db_engine.connect() as connection:
        df = pd.read_sql(query, connection, params=params)
        # print("test")
        print(df)

    # Check if the DataFrame is empty
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
            "start_time": start_time,
            "end_time": end_time,
        }

    df['time_input'] = pd.to_datetime(df['time_input'])
    # print(f"1:{df}")

    df["date"] = df["time_input"].dt.date
    # print(f"2:{df}")

    df["time"] = df["time_input"].dt.time
    # print(f"3:{df}")
    dff = df.groupby(["action"]).time_taken.sum().reset_index()
    print(dff)

    # filtered_df = df
    filtered_df = df[(df["action"] == "abnormal_cycle") | (df["action"] == "downtime")].copy()
    # print(filtered_df)
    start_time = df["time_input"].min()
    end_time = df["time_input"].max()

    total_stop = len(df[df["action"] == "downtime"])
    total_shots = len(df[df["action"] == "normal_cycle"])
    total_running = dff['time_taken'].sum()
    median_cycle_time = round(df["time_taken"].median(), 2)

    cycle_time = df['cycle_time'].values[0]  # Safe to access now
    ideal_time = total_shots * cycle_time
    downtime = dff['time_taken'].values[1]

    efficiency = ((total_shots * cycle_time) / total_running) * 100


        # Ensure time_taken is numeric
    filtered_df["time_taken"] = pd.to_numeric(filtered_df["time_taken"], errors="coerce")

    # Sort by time_input to ensure proper sequence
    filtered_df = filtered_df.sort_values(by="time_input").reset_index(drop=True)
    print(filtered_df)
    filtered_df["total_minutes"] = filtered_df["time_taken"] / 60
    filtered_df["total_minutes"] = filtered_df["total_minutes"].round(2)

    total_downtime = filtered_df["time_taken"].sum() / 60
    print(f"Total Downtime: {total_downtime.round(2)} minutes")

    # Create a list to store the merged rows
    # merged_rows = []

    # i = 0
    # while i < len(filtered_df) - 1:
    #     current_row = filtered_df.iloc[i]
    #     next_row = filtered_df.iloc[i + 1]

    #     if current_row["action"] == "abnormal_cycle" and next_row["action"] == "downtime":
    #         combined = current_row.copy()
    #         combined["action"] = "downtime"
    #         combined["time_taken"] = current_row["time_taken"] + next_row["time_taken"]
    #         combined["total_minutes"] = combined["time_taken"] / 60
    #         merged_rows.append(combined)
    #         i += 2  # Skip next row
    #     else:
    #         i += 1  # Move to next row

    # # Convert list to DataFrame
    # result_df = pd.DataFrame(merged_rows)
    # print(f"4:{result_df}")
    # Optional: round the time columns
    # result_df["time_taken"] = result_df["time_taken"].round(2)
    # result_df["total_minutes"] = result_df["total_minutes"].round(2)
    # result_df = result_df[["idmonitoring", "time_input", "time_taken", "total_minutes"]]

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
    with db_connection_str.connect() as connection:

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
        with db_connection_str.connect() as connection:
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



    # print(daily
# date = datetime.strptime("2025-06-16", "%Y-%m-%d").replace(hour=8, minute=0, second=0, microsecond=0)
# df = daily_report(date)
# print(df)

# shift1_totaldt = df["shift_1_downtime_minutes"].sum()
# shift2_totaldt = df["shift_2_downtime_minutes"].sum()
# overall_totaldt = df["shift_1_downtime_minutes"].sum() + df["shift_2_downtime_minutes"].sum()
# print(f"Overall Total Downtime: {overall_totaldt} minutes")
# print(f"Shift 1 Total Downtime: {shift1_totaldt} minutes")
# print(f"Shift 2 Total Downtime: {shift2_totaldt} minutes")



# ov, de = fetch_data_monthly("A6")
# print(ov,de)
# df , _ = calculate_downtime_daily_report(192, "2025-06-16")
# print(df)
# # Assuming df is your DataFrame and is already sorted by time_input
# # Ensure time_taken is numeric
# df["time_taken"] = pd.to_numeric(df["time_taken"], errors="coerce")

# # Sort by time_input to ensure proper sequence
# df = df.sort_values(by="time_input").reset_index(drop=True)

# # Create a list to store the merged rows
# merged_rows = []

# i = 0
# while i < len(df) - 1:
#     current_row = df.iloc[i]
#     next_row = df.iloc[i + 1]

#     if current_row["action"] == "abnormal_cycle" and next_row["action"] == "downtime":
#         combined = current_row.copy()
#         combined["action"] = "downtime"
#         combined["time_taken"] = current_row["time_taken"] + next_row["time_taken"]
#         combined["total_minutes"] = combined["time_taken"] / 60
#         merged_rows.append(combined)
#         i += 2  # Skip next row
#     else:
#         i += 1  # Move to next row

# # Convert list to DataFrame
# result_df = pd.DataFrame(merged_rows)

# # Optional: round the time columns
# result_df["time_taken"] = result_df["time_taken"].round(2)
# result_df["total_minutes"] = result_df["total_minutes"].round(2)

# print(result_df[["idmonitoring", "time_input", "time_taken", "total_minutes"]])

# # test = monthly()
# # print(test)
# df = daily_report()


# print(df)



# test = hourly(79)
# print(test)