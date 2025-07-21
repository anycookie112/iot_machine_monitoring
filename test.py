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

    # Reorder columns to place 'total_stops' after 'mould_id'
    cols = list(merged.columns)
    if 'total_stops' in cols and 'mould_id' in cols:
        cols.remove('total_stops')
        mould_index = cols.index('mould_id')
        cols.insert(mould_index + 1, 'total_stops')
        merged = merged[cols]
    
    mp_id_list = merged["mp_id"].tolist()


    return merged, {"shift_1_totaldt": shift1_totaldt, "shift_2_totaldt": shift2_totaldt, "overall_totaldt": overall_totaldt}, mp_id_list


def hourly(mp_id=None, date=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    
    start, _, end = date_calculation(date)
    
    if mp_id:
        df, _ = calculate_downtime(mp_id)
        df["time_input"] = pd.to_datetime(df["time_input"])

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



def get_main_id(mp_id):
    query = text("""
        SELECT DISTINCT main_id 
        FROM machine_monitoring.monitoring
        WHERE mp_id IN :mp_id;
    """)
    
    with db_connection_str.connect() as connection:
        df_filtered = pd.read_sql(query, connection, params={"mp_id": tuple(mp_id)})

    return df_filtered["main_id"].tolist()


    # query = text("""SELECT action, time_taken, time_input FROM machine_monitoring.monitoring
    #             where main_id = :main_id
    #             limit 2""")
    
    # with db_connection_str.connect() as connection:
    #     df_change_mould_info = pd.read_sql(query, connection, params={
    #         "main_id": main_id,
    #     })
    # df_dict = df_change_mould_info.to_dict(orient='records')



def get_mould_activities(date):
    
    start_date, mid_time, end_date = date_calculation_new(date)
    query = text("""SELECT monitoring.main_id, machine_code, mould_code, monitoring.action, time_taken, monitoring.time_input, monitoring.remarks
            FROM monitoring
            inner join joblist
            on monitoring.main_id = joblist.main_id
            WHERE action IN ('adjustment', 'change mould')
            AND monitoring.time_input between :start_date AND :end_date;
            """)    
    
    with db_connection_str.connect() as connection:
        df = pd.read_sql(query, connection, params={
            "start_date": start_date,
            "end_date": end_date
        })

    # Convert to datetime
    df['time_input'] = pd.to_datetime(df['time_input'])

    # Rename time_input to time_ended
    df.rename(columns={'time_input': 'time_ended'}, inplace=True)

    # Convert time_taken to hours
    df['time_taken_hr'] = (df['time_taken'] / 3600).round(2)


    # Compute time_start
    df['time_start'] = df.apply(
        lambda row: row['time_ended'] - timedelta(seconds=row['time_taken']) if pd.notnull(row['time_taken']) else pd.NaT,
        axis=1
    )
    df['time_start'] = df['time_start'].dt.strftime('%H:%M')
    df['time_ended'] = df['time_ended'].dt.strftime('%H:%M')


    # Optional: reorder or drop old column
    df = df[['main_id', 'machine_code', 'mould_code', 'action', 'time_taken_hr', 'time_start', 'time_ended', 'remarks']]

    # Ensure time_taken_hr is numeric
    df['time_taken_hr'] = pd.to_numeric(df['time_taken_hr'], errors='coerce')

    # Filter and sum
    change_mould_total = df[df['action'] == 'change mould']['time_taken_hr'].sum()
    adjustment_total = df[df['action'] == 'adjustment']['time_taken_hr'].sum()
    return df, change_mould_total, adjustment_total

    

def calculate_efficiency_daily():
    """
    
    get all rows of a certain mp_id on the day
    sum all the rows on actions

    shift 1 efficiency
    shift 2 efficiency
    overall effciency

    efficiency = actual_time / total time

    number of shots = sum of row where action = normal cycle

    get main id join onto job list where main_id 
    and mould id join onto mould list 

    so efficiency will based on mp_id ?

    
    """

    pass

# print(get_main_id(250))



def get_mould_info(main_id):
    # main_id_list = get_main_id(mp_id)

    # if not main_id_list:
    #     return []

    query1 = text("""
        SELECT DISTINCT main_id, part_name, part_code, cycle_time_rev 
        FROM machine_monitoring.joblist AS j
        JOIN machine_monitoring.mould_list AS ml 
            ON j.mould_code = ml.mould_code
        WHERE main_id IN :main_ids
    """)

    with db_connection_str.connect() as connection:
        df_filtered = pd.read_sql(query1, connection, params={
            "main_ids": tuple(main_id)
        })

    # If you only want data for the first main_id for the second query


    df_unique = df_filtered.drop_duplicates(subset="main_id", keep="first")


    return df_unique


def unpivot():
    query = text("""
        SELECT monitoring.main_id, mp_id, action, time_taken
        FROM machine_monitoring.monitoring AS monitoring
        WHERE monitoring.time_input BETWEEN '2025-07-17' AND '2025-07-18'
    """)

    with db_connection_str.connect() as connection:
        df = pd.read_sql(query, connection)

    # Count how many times each (main_id, mp_id) had a 'normal_cycle' action
    df_normal_cycle_count = (
        df[df["action"] == "normal_cycle"]
        .groupby(["main_id", "mp_id"])
        .size()
        .reset_index(name="normal_cycle_count")
    )

    # Group and sum time_taken for each action
    df_grouped = (
        df.groupby(["main_id", "mp_id", "action"], as_index=False)["time_taken"].sum()
    )

    # Pivot to make actions columns
    df_pivot = df_grouped.pivot(
        index=["main_id", "mp_id"],
        columns="action",
        values="time_taken"
    ).reset_index()

    df_result = pd.merge(df_pivot, df_normal_cycle_count, on=["main_id", "mp_id"], how="left")

    # Optional: Fill NaN with 0
    df_result["normal_cycle_count"] = df_result["normal_cycle_count"].fillna(0).astype(int)

    main_id_list = df_pivot["main_id"].tolist()

    mould_info = get_mould_info(main_id_list)

    # # 3. (Optional) Flatten column names
    # df_pivot.columns.name = None  # Remove the 'action' label on the columns

    df_joined = pd.merge(df_result, mould_info, on="main_id", how="inner")  # or "left", "right", "outer"

    # Replace NaNs in downtime and abnormal_cycle with 0
    df_joined["downtime"] = df_joined["downtime"].fillna(0)
    df_joined["abnormal_cycle"] = df_joined["abnormal_cycle"].fillna(0)

    # Calculate total time
    df_joined["total_time"] = df_joined["abnormal_cycle"] + df_joined["downtime"] + df_joined["normal_cycle"]

    # Calculate efficiency
    df_joined["efficiency"] = (
        (df_joined["cycle_time_rev"] * df_joined["normal_cycle_count"]) / df_joined["total_time"]
    ) * 100

    df_joined["efficiency"] = df_joined["efficiency"].round(2)


    print(df_joined)
    # return df_pivot

# df, x, y = get_mould_activities("2025-07-02")
# print(df, x,y)

# print(get_mould_info(250))





# print(main_id)


# x,y, mp_id = daily_report()

# main_id = get_mould_info(mp_id)

# print(mp_id)
unpivot()


"""

in theory 
machine a


so find the stast time of each machine 
and end time 
based on that calculate the hours

so like 8-8 means 24 hours
3-6 means 3 hours

based on machine 
so means i see the machine on specific day what is start and stop



so join table
query first and last log of machine 




"""