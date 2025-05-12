import pandas as pd
from sqlalchemy import create_engine,text
from datetime import datetime
import os
import sys
from config.config import DB_CONFIG
# from utils.daily import date_calculation

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



def calculate_downtime(mp_id):
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://root:UL1131@192.168.1.15/machine_monitoring'

    db_engine = create_engine(db_connection_str)
    
    if not mp_id:  # Check if mp_id is None or empty
        print("Error: mp_id is None or empty")
        return pd.DataFrame(), None  # Return an empty DataFrame to prevent errors
    

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
    dff = df.groupby(["action"]).time_taken.sum().reset_index()
    
    
    filtered_df = df[(df["action"] == "abnormal_cycle") | (df["action"] == "downtime")]
    # print(filtered_df)
    start_time = df["time_input"].min()
    end_time = df["time_input"].max()

    total_stop = len(df[df["action"]== "downtime"])
    total_shots = len(df[df["action"]== "normal_cycle"])
    total_running = dff['time_taken'].sum()
    median_cycle_time = round(df["time_taken"].median(), 2)

    cycle_time = df['cycle_time'].values[0]
    # print(cycle_time)
    ideal_time = total_shots * cycle_time
    downtime = dff['time_taken'].values[1]
    # print(df)

    efficiency = ((total_shots * cycle_time) / (total_running)) * 100

    # return { "production_time": total_running, "ideal_time":ideal_time, "downtime": downtime, "efficiency": efficiency , "total_times_stoped": total_stop, "total_shots": total_shots}
    return filtered_df, { "production_time": total_running, "ideal_time":ideal_time, "downtime": downtime, "efficiency": efficiency , "total_times_stoped": total_stop, "median_cycle_time": median_cycle_time, "total_shots": total_shots,"start_time": start_time,"end_time": end_time}


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


def calculate_downtime_df_daily_report(mp_id, date= datetime.now().date()):
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    db_engine = create_engine(db_connection_str)

    # SQL query with an additional WHERE clause for the date
    query = f"""
        SELECT DISTINCT m.*, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_list AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id IN ({mp_id})
        AND DATE(m.time_input) = '{date}'
        ORDER BY m.time_input;
    """
    
    # Execute the query and process the DataFrame
    df = pd.read_sql(query, con=db_engine)
    df['time_input'] = pd.to_datetime(df['time_input'])
    df["date"] = df["time_input"].dt.date
    df["time"] = df["time_input"].dt.time
    df['time_diff'] = df['time_input'].diff().dt.total_seconds()
    df['downtime'] = df['time_diff'] - df['cycle_time']

    # Calculate outliers using IQR
    Q1 = df['time_taken'].quantile(0.25)
    Q3 = df['time_taken'].quantile(0.75)
    IQR = Q3 - Q1
    threshold = 2
    outliers = df[(df['time_taken'] < Q1 - threshold * IQR) | (df['time_taken'] > Q3 + threshold * IQR)]

    return outliers, df

# def calculate_downtime_daily_report(mp_id, date= datetime.now().date()):
#     # Connect to the database
#     db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
#     # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
#     # db_connection_str = 'mysql+pymysql://root:UL1131@192.168.1.15/machine_monitoring'

#     db_engine = create_engine(db_connection_str)
    
#     if not mp_id:  # Check if mp_id is None or empty
#         print("Error: mp_id is None or empty")
#         return pd.DataFrame(), None  # Return an empty DataFrame to prevent errors
    
#     start_time, mid_time, end_time = date_calculation(date)

#     query = f"""
#         SELECT DISTINCT m.*, mm.cycle_time 
#         FROM monitoring AS m
#         JOIN joblist AS j ON m.main_id = j.main_id
#         JOIN mould_list AS mm ON j.mould_code = mm.mould_code
#         WHERE m.mp_id IN ({mp_id})
#         AND DATE(m.time_input) BETWEEN :start_time AND :end_time
#         ORDER BY m.time_input;
#         """

# #so the query has to get the date 
    
#     df = pd.read_sql(query, con=db_engine)
#     df['time_input'] = pd.to_datetime(df['time_input'])
#     df["date"] = df["time_input"].dt.date
#     df["time"] = df["time_input"].dt.time
#     dff = df.groupby(["action"]).time_taken.sum().reset_index()
    
    
#     filtered_df = df[(df["action"] == "abnormal_cycle") | (df["action"] == "downtime")]
#     # print(filtered_df)
#     start_time = df["time_input"].min()
#     end_time = df["time_input"].max()

#     total_stop = len(df[df["action"]== "downtime"])
#     total_shots = len(df[df["action"]== "normal_cycle"])
#     total_running = dff['time_taken'].sum()
#     median_cycle_time = round(df["time_taken"].median(), 2)

#     cycle_time = df['cycle_time'].values[0]
#     # print(cycle_time)
#     ideal_time = total_shots * cycle_time
#     downtime = dff['time_taken'].values[1]
#     # print(df)

#     efficiency = ((total_shots * cycle_time) / (total_running)) * 100

#     # return { "production_time": total_running, "ideal_time":ideal_time, "downtime": downtime, "efficiency": efficiency , "total_times_stoped": total_stop, "total_shots": total_shots}
#     return filtered_df, { "production_time": total_running, "ideal_time":ideal_time, "downtime": downtime, "efficiency": efficiency , "total_times_stoped": total_stop, "median_cycle_time": median_cycle_time, "total_shots": total_shots,"start_time": start_time,"end_time": end_time}

mp_id = 99
update_sql(mp_id)
# outliers_df, full_df = calculate_downtime_df(mp_id)

df, result2 = calculate_downtime(mp_id)

# # print(len(outliers_df))
# # print(full_df)
# # avg = full_df["time_taken"].median()
# print(df)
# print(result2)

