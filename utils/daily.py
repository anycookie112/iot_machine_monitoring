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
            "max_cycle_time": round(Q1, 2),
            "median_cycle_time": round(median, 2),
            "min_cycle_time": round(Q3, 2),
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


def fetch_data(start_time ,mid_time , end_time ):
    # query = text("""
        # SELECT monitoring.*, production.mould_id, production.machine_code
        # FROM machine_monitoring.monitoring AS monitoring
        # INNER JOIN machine_monitoring.mass_production AS production
        #     ON monitoring.mp_id = production.mp_id
        # WHERE monitoring.time_input BETWEEN :start_time AND :end_time
        # AND monitoring.action IN ('downtime');
    # """)

    query = text("""
    SELECT
        monitoring.*,
        MAX(production.mould_id) AS mould_id,
        MAX(production.machine_code) AS machine_code,
        MAX(ml.standard_ct) AS standard_ct
    FROM machine_monitoring.monitoring AS monitoring
    INNER JOIN machine_monitoring.mass_production AS production
        ON monitoring.mp_id = production.mp_id
    INNER JOIN machine_monitoring.mould_list AS ml
        ON production.mould_id = ml.mould_code
    WHERE monitoring.time_input BETWEEN :start_time AND :end_time
    AND monitoring.action IN ('downtime')
    GROUP BY monitoring.idmonitoring;
    """)

    # query2 = text("""
    #     SELECT monitoring.*, production.mould_id, production.machine_code
    #     FROM machine_monitoring.monitoring AS monitoring
    #     INNER JOIN machine_monitoring.mass_production AS production
    #         ON monitoring.mp_id = production.mp_id
    #     WHERE monitoring.time_input BETWEEN :start_time AND :end_time
    #     AND monitoring.action IN ('normal_cycle');
    # """)

    query2 = text("""
    SELECT 
        monitoring.*,
        MAX(mp.mould_id) AS mould_id,
        MAX(mp.machine_code) AS machine_code,
        MAX(ml.standard_ct) AS standard_ct
    FROM machine_monitoring.monitoring AS monitoring
    INNER JOIN machine_monitoring.mass_production AS mp
        ON monitoring.mp_id = mp.mp_id
    INNER JOIN machine_monitoring.mould_list AS ml
        ON mp.mould_id = ml.mould_code
    WHERE monitoring.time_input BETWEEN :start_time AND :end_time
    AND monitoring.action = 'normal_cycle'
    GROUP BY monitoring.idmonitoring;  

    """)

    # Run query and load into a DataFrame
    with db_connection_str.connect() as connection:

        df_unique = pd.read_sql(query2, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })



        # Get unique machine_code and corresponding mould_id
        machines_running = df_unique.groupby(["mp_id", "machine_code", "standard_ct"])["mould_id"].first().reset_index()
        # print(machines_running)

        # # Convert to DataFrame
        # df_main = pd.DataFrame(machines_running)
        # # print(df_main)

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
    # print(df_unique_raw, shift1, shift2)

    # If there's no data at all, return an empty DataFrame with the expected columns
    if shift1.empty and shift2.empty and df_unique_raw.empty:
        return (
            pd.DataFrame(columns=[
                "mp_id", "machine_code", "mould_id", "total_stops",
                "shift_1_stops", "shift_1_downtime",
                "shift_2_stops", "shift_2_downtime", "standard_ct",
                # add any other columns expected from information_df below
            ]),
            {"shift_1_totaldt": 0, "shift_2_totaldt": 0, "overall_totaldt": 0}
        )

    information_df = fetch_data_variation(date)

    if not information_df.empty:
        information_df = calculate_filtered_variance_by_group(information_df, "mp_id", "time_taken")

    # Ensure df_unique has one row per mp_id
    df_unique = df_unique_raw[["mp_id", "machine_code", "mould_id", "standard_ct"]].drop_duplicates(subset="mp_id")

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
    
    start, _, end = date_calculation(date)
    
    if mp_id:
        df, _ = calculate_downtime(mp_id)
        df["time_input"] = pd.to_datetime(df["time_input"])

        # Filter to the defined date range
        df = df[(df["time_input"] >= start) & (df["time_input"] < end)]

        # Split downtime and abnormal_cycle
        df_downtime = df[df["action"] == "downtime"].copy()
        df_abnormal = df[df["action"] == "abnormal_cycle"].copy()

        # Assign hour and shift for both
        for d in [df_downtime, df_abnormal]:
            d["hour"] = d["time_input"].dt.hour
            d["shift"] = d["time_input"].apply(
                lambda x: "Shift 1" if 8 <= x.hour < 20 else "Shift 2"
            )

        # Group both
        grouped_downtime = df_downtime.groupby(["shift", "hour"]).size().reset_index(name="stops")
        grouped_abnormal = df_abnormal.groupby(["shift", "hour"]).size().reset_index(name="stops_abnormal")

        # Fill in all hours for Shift 1 (8–19) and Shift 2 (20–23 and 0–7)
        shift1_hours = pd.DataFrame({"hour": range(8, 20)})
        shift2_hours = pd.DataFrame({"hour": list(range(20, 24)) + list(range(0, 8))})

        def merge_shift(shift_hours, shift_name):
            merged = (
                shift_hours
                .merge(grouped_downtime[grouped_downtime["shift"] == shift_name], on="hour", how="left")
                .merge(grouped_abnormal[grouped_abnormal["shift"] == shift_name], on="hour", how="left")
                .fillna(0)
                .infer_objects(copy=False)
            )
            merged["stops"] = merged["stops"].astype(int)
            merged["stops_abnormal"] = merged["stops_abnormal"].astype(int)
            merged["shift"] = shift_name
            return merged

        shift1 = merge_shift(shift1_hours, "Shift 1")
        shift2 = merge_shift(shift2_hours, "Shift 2")

        return shift1, shift2
    else:
        print("No MP ID provided.")
        return pd.DataFrame(), pd.DataFrame()

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


 
    
    query = """
        SELECT DISTINCT m.*, mm.standard_ct 
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
        # print(df)

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
    # print(dff)

    # filtered_df = df
    filtered_df = df[(df["action"] == "abnormal_cycle") | (df["action"] == "downtime")].copy()
    # print(filtered_df)
    start_time = df["time_input"].min()
    end_time = df["time_input"].max()

    total_stop = len(df[df["action"] == "downtime"])
    total_shots = len(df[df["action"] == "normal_cycle"])
    total_running = dff['time_taken'].sum()
    median_cycle_time = round(df["time_taken"].median(), 2)

    cycle_time = df['standard_ct'].values[0]  
    ideal_time = total_shots * cycle_time
    downtime = dff['time_taken'].values[1]

    efficiency = ((total_shots * cycle_time) / total_running) * 100


        # Ensure time_taken is numeric
    filtered_df["time_taken"] = pd.to_numeric(filtered_df["time_taken"], errors="coerce")

    # Sort by time_input to ensure proper sequence
    filtered_df = filtered_df.sort_values(by="time_input").reset_index(drop=True)
    # print(filtered_df)
    filtered_df["total_minutes"] = filtered_df["time_taken"] / 60
    filtered_df["total_minutes"] = filtered_df["total_minutes"].round(2)

    total_downtime = filtered_df["time_taken"].sum() / 60
    # print(f"Total Downtime: {total_downtime.round(2)} minutes")


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

def get_main_id (mp_id):

    query = text (f"""SELECT main_id FROM machine_monitoring.monitoring
                where mp_id = :mp_id
                limit 1 """)
    
    with db_connection_str.connect() as connection:
        df_filtered = pd.read_sql(query, connection, params={
            "mp_id": mp_id,
        })

    main_id = df_filtered["main_id"].loc[0]

    query = text("""SELECT action, time_taken, time_input FROM machine_monitoring.monitoring
                where main_id = :main_id
                limit 2""")
    
    with db_connection_str.connect() as connection:
        df_change_mould_info = pd.read_sql(query, connection, params={
            "main_id": main_id,
        })
    df_dict = df_change_mould_info.to_dict(orient='records')

    return df_dict






def mould_activities (date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start_time, _, end_time = date_calculation(date)

    query = text("""
    SELECT 
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

    with db_connection_str.connect() as connection:

        df = pd.read_sql(query, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })

    # Convert to datetime
    df['time_input'] = pd.to_datetime(df['time_input'])

    # Normalize action
    df['base_action'] = df['action'].str.replace(r' (start|end)$', '', regex=True)

    # Group start times
    start_df = (
        df[df['action'].str.endswith('start')]
        .groupby(['main_id', 'base_action', 'machine_code', 'mould_code'], as_index=False)
        .agg(start_time=('time_input', 'min'))
    )

    # Group end times and handle part_name/remarks
    end_df = (
        df[df['action'].str.endswith('end')]
        .groupby(['main_id', 'base_action'], as_index=False)
        .agg(
            end_time=('time_input', 'max'),
            remarks=('remarks', lambda x: ', '.join(sorted(set(filter(None, x))))),
            part_name=('part_name', lambda x: ', '.join(sorted(set(filter(None, x)))))
        )
    )

    # Merge safely (one-to-one now)
    merged = pd.merge(start_df, end_df, on=['main_id', 'base_action'], how='inner')

    # Compute duration
    merged['duration'] = merged['end_time'] - merged['start_time']
    merged['duration_hr'] = (merged['duration'].dt.total_seconds() / 3600).round(2)

    # Totals
    change_mould_total = merged[merged['base_action'] == 'change mould']['duration_hr'].sum()
    adjustment_total = merged[merged['base_action'] == 'adjustment']['duration_hr'].sum()

    return (
        merged[['machine_code', 'mould_code', 'part_name', 'main_id', 'base_action', 'start_time', 'end_time', 'duration_hr', 'remarks']],
        change_mould_total,
        adjustment_total
    )



def efficiency_sql_only (date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start_time, _, end_time = date_calculation(date)
    query = text("""

        SELECT 
            mass_production.machine_code,
            
            SUM(monitoring.time_taken)/3600 AS total_time_taken,

            SUM(CASE WHEN monitoring.action = 'normal_cycle' THEN monitoring.time_taken ELSE 0 END) /3600 AS normal_cycle_time,
            SUM(CASE WHEN monitoring.action = 'abnormal_cycle' THEN monitoring.time_taken ELSE 0 END)/3600 AS abnormal_cycle_time,
            SUM(CASE WHEN monitoring.action = 'downtime' THEN monitoring.time_taken ELSE 0 END)/3600 AS downtime_time,

            SUM(CASE WHEN monitoring.action = 'normal_cycle' THEN 1 ELSE 0 END) AS shot_count,

            MIN(monitoring.time_input) AS first_input_time,
            MAX(monitoring.time_input) AS last_input_time,
            TIMEDIFF(MAX(monitoring.time_input), MIN(monitoring.time_input)) AS total_running_time,

            ROUND(
                SUM(CASE WHEN monitoring.action = 'normal_cycle' THEN monitoring.time_taken ELSE 0 END) / 
                SUM(monitoring.time_taken) * 100, 
                2
            ) AS efficiency_percent



        FROM 
            mass_production
        INNER JOIN monitoring ON monitoring.mp_id = mass_production.mp_id
        WHERE 
            monitoring.time_input BETWEEN :start_time AND :end_time
        GROUP BY 
            mass_production.machine_code;
        """)

        # Run query and load into a DataFrame
    with db_connection_str.connect() as connection:
        df = pd.read_sql(query, connection, params={
            "start_time": start_time,
            "end_time": end_time
        })

    if df.empty:
        return df, 0.0, 0.0, 0.0, 0.0

    # Convert to timedelta
    df['total_running_time'] = pd.to_timedelta(df['total_running_time'])

    # Add downtime column (24h - normal cycle time)
    df['downtime'] = 24 - df['normal_cycle_time']
    df['efficiency'] = (df['normal_cycle_time'] / 24 * 100).round(2)

    # Drop if not needed later
    df = df.drop(columns=['total_running_time'])  

    # Summary calculations
    actual_total_gain_hr = df['normal_cycle_time'].sum()
    ideal_overall_machine_capacity = 24 * 20
    act_avail_hr = df["total_time_taken"].sum() 

    actual_running_machines = len(df) * 24

    # over_act_eff = round((actual_total_gain_hr / act_avail_hr) * 100, 2)
    over_act_eff = round((actual_total_gain_hr / ideal_overall_machine_capacity) * 100, 2)

    ovr_mc_capacity = round((actual_total_gain_hr / ideal_overall_machine_capacity) * 100, 2)
    actual_mc_capacity = round((actual_total_gain_hr / actual_running_machines) * 100, 2) 
    overall_eff = round((df['efficiency_percent'].sum() / len(df)), 2)

    if df.empty:
        return df, 0, 0, 0, 0
    else:
        return df, over_act_eff, ovr_mc_capacity, overall_eff, actual_mc_capacity



def combined_output(date):
    df_summary, actual_machine_capacity_overall, actual_capacity_running, overall_eff, actual_mc_capacity = efficiency_sql_only(date)
    df_actions, x, y = mould_activities(date)

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

    # Add missing columns with 0 if not in pivoted actions
    for col in ['total_change_mould_hr', 'total_adjustment_hr']:
        if col not in pivot_actions.columns:
            pivot_actions[col] = 0

    df_merged = df_summary.merge(pivot_actions, on='machine_code', how='left')

    df_merged[['total_change_mould_hr', 'total_adjustment_hr']] = df_merged[
        ['total_change_mould_hr', 'total_adjustment_hr']].fillna(0)

    # Add adjustment & mould change time into total_time_taken
    df_merged['total_time_taken'] = (
        df_merged['total_time_taken']
        + df_merged['total_adjustment_hr']
        + df_merged['total_change_mould_hr']
    )


    df_merged['machine_capacity'] = (df_merged['normal_cycle_time'] / 24  * 100 ).round(2)

    # Create totals for all numeric columns you care about
    numeric_cols = [
        'total_time_taken',
        'normal_cycle_time',
        'abnormal_cycle_time',
        'downtime_time',
        'total_adjustment_hr',
        'total_change_mould_hr',
        'downtime'
    ]

        # Totals for numeric columns
    df_merged.loc['Total', numeric_cols] = df_merged[numeric_cols].sum().round(2)

    # Aggregate metrics instead of blanking
    df_merged.loc['Total', 'efficiency'] = round(df_merged['efficiency'].mean(), 2) if not df_merged['efficiency'].empty else 0.0


    
    df_merged.loc['Total', 'machine_capacity'] = round(df_merged['machine_capacity'].mean(), 2) if not df_merged['machine_capacity'].empty else 0.0
    df_merged.loc['Total', 'shot_count'] = round(df_merged['shot_count'].mean(), 2) if not df_merged['shot_count'].empty else 0.0

    # Clear non-summed columns
    for col in ['machine_code', 'first_input_time', 'last_input_time']:
        df_merged[col] = df_merged[col].astype("object")
        df_merged.loc['Total', col] = ''

    # Reorder columns
    desired_order = [
        'machine_code',
        'total_time_taken', 
        'normal_cycle_time',
        'downtime',
        # 'abnormal_cycle_time',
        # 'downtime_time',
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
    
    return df_merged, actual_machine_capacity_overall, actual_capacity_running, overall_eff, actual_mc_capacity
    




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

