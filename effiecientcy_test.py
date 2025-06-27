import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import os
import sys
from config.config import DB_CONFIG
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def calculate_downtime(mp_id):
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://root:UL1131@192.168.1.15/machine_monitoring'

    db_engine = create_engine(db_connection_str)

    query = f"""
        SELECT DISTINCT m.*, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_list AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id IN ({mp_id})
        ORDER BY m.time_input;
        """
    
    df = pd.read_sql(query, con=db_engine)
    df_var = df[df["action"] == "normal_cycle"] 
    dff = df.groupby(["action"]).time_taken.sum().reset_index()
    filtered_df = df[(df["action"] == "abnormal_cycle") | (df["action"] == "downtime")]
    # print(filtered_df)


    total_stop = len(df[df["action"]== "abnormal_cycle"])
    total_shots = len(df[df["action"]== "normal_cycle"])
    total_running = dff['time_taken'].sum()
    median_cycle_time = print(round(df["time_taken"].median(), 2))

    cycle_time = df['cycle_time'].values[0]
    # print(cycle_time)
    ideal_time = total_shots * cycle_time
    downtime = dff['time_taken'].values[1]
    # print(dff)

    efficiency = ((total_shots * cycle_time) / (total_running)) * 100
    print(df)
    print(f"shots{total_shots}")
    print(f"cycle{cycle_time}")
    print(f"total run{total_running}")

    return filtered_df, { "production_time": total_running, "ideal_time":ideal_time, "downtime": downtime, "efficiency": efficiency , "total_times_stoped": total_stop, "median_cycle_time": median_cycle_time}

def calculate_downtime_df(mp_id):
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://root:UL1131@192.168.1.15/machine_monitoring'
    db_engine = create_engine(db_connection_str)

    query = f"""
        SELECT DISTINCT m.*, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_list AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id IN ({mp_id})
        ORDER BY m.time_input;

        """
    
    df = pd.read_sql(query, con=db_engine)

    df['time_input'] = pd.to_datetime(df['time_input'])
    df["date"] = df["time_input"].dt.date
    df["time"] = df["time_input"].dt.time
    df['time_diff'] = df['time_input'].diff().dt.total_seconds()
    df['downtime'] = df['time_diff'] - df['cycle_time']

    Q1 = df['time_taken'].quantile(0.25)
    Q3 = df['time_taken'].quantile(0.75)
    IQR = Q3 - Q1
    threshold = 2
    outliers = df[(df['time_taken'] < Q1 - threshold * IQR) | (df['time_taken'] > Q3 + threshold * IQR)]

    return outliers,df

def update_sql(mp_id, complete = False):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    connection = create_engine(db_connection_str).raw_connection()
    with connection.cursor() as cursor:
        dummy, information = calculate_downtime(mp_id)
        # print(information["ideal_time"])
        if complete == False:
            sql_update = "update mass_production set total_production_time = %s, downtime = %s, efficiency = %s where mp_id = %s "
            cursor.execute(sql_update, (information["production_time"], information["downtime"], information["efficiency"], mp_id,))
            connection.commit()
            """
            so in the mass production table, get the mpid 
            update mass_production set total_production_time = %s, total_down_time = %s, efficiency = %s
            where mp_id = %s 
            """
        else:
            sql_update = "update mass_production set total_production_time = %s, downtime = %s, efficiency = %s, status = %s, time_completed = %s where mp_id = %s "
            cursor.execute(sql_update, (information["production_time"], information["downtime"], information["efficiency"], "completed", current_time, mp_id,))
            connection.commit()
            """
            so in the mass production table, get the mpid 
            update mass_production set total_production_time = %s, total_down_time = %s, efficiency = %s
            where mp_id = %s 
            """

mp_id = 99
update_sql(mp_id)
# outliers_df, full_df = calculate_downtime_df(mp_id)

df2, info = calculate_downtime(mp_id)

print(df2)
print(info)
# print(len(outliers_df))
# print(full_df)
# avg = full_df["time_taken"].median()
# print(avg)
# print(result2)

import pandas as pd

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
    print(Q1)
    Q3 = df[column_name].quantile(0.90)
    print(Q3)
    IQR = Q3 - Q1

    # Define the lower and upper bounds for filtering
    lower_bound = Q1 - threshold * IQR
    upper_bound = Q3 + threshold * IQR

    # Filter the DataFrame to exclude outliers
    filtered_df = df[(df[column_name] >= lower_bound) & (df[column_name] <= upper_bound)]

    # Calculate and return the variance of the filtered column
    return filtered_df[column_name].var()

# Example usage
# data = {
#     'time_taken': [10, 12, 15, 14, 100, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
# }
# df = pd.DataFrame(data)

# variance = calculate_filtered_variance(df, 'time_taken')
# print(f"Filtered Variance: {variance}")

"""
total production running time
query monitoring all 
sum all in time taken column

total times stopped
count of abnormal function


total downtime 
sum of timetaken where action = downtime & 
"""