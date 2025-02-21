import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

def calculate_downtime(mp_id):
    # Connect to the database
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    db_engine = create_engine(db_connection_str)

    # Query the database
    query = f"""
        SELECT m.*, j.mould_code, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_masterlist AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id in ({mp_id})
        ORDER BY m.time_input;
    """
    
    df = pd.read_sql(query, con=db_engine)
    df["time_input"] = pd.to_datetime(df["time_input"])
    df["date"] = df["time_input"].dt.date
    df["time"] = df["time_input"].dt.time
    df["cycle_start_time"] = df["time_input"] - pd.to_timedelta(df["time_taken"], unit="s")

    # Given ideal cycle time
    ideal_cycle_time = df["cycle_time"].loc[0]  # seconds

    df["downtime"] = (df["time_input"].diff().dt.total_seconds() - df["cycle_time"]).shift(-1)



    # Fill NaN downtime (last row) with 0
    df["downtime"] = df["downtime"].fillna(0)
    tolerance = ideal_cycle_time * 0.05
    #filter values outside ±tolerance
    df = df[df['downtime'].abs() > tolerance]
    
    total_ideal_time = len(df.index) * ideal_cycle_time
    total_downtime = df['downtime'].sum()
    total_production_time = df['time_taken'].sum()
    efficiency = (total_ideal_time /(total_production_time + total_downtime)) * 100

    return { "production_time": total_production_time, "ideal_time":total_ideal_time, "downtime": total_downtime, "efficiency": efficiency }

def calculate_downtime_df(mp_id):
    # Connect to the database
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    db_engine = create_engine(db_connection_str)

    # Query the database
    query = f"""
        SELECT m.*, j.mould_code, mm.cycle_time 
        FROM monitoring AS m
        JOIN joblist AS j ON m.main_id = j.main_id
        JOIN mould_masterlist AS mm ON j.mould_code = mm.mould_code
        WHERE m.mp_id in ({mp_id})
        ORDER BY m.time_input;
    """
    df = pd.read_sql(query, con=db_engine)
    df["time_input"] = pd.to_datetime(df["time_input"])
    df["date"] = df["time_input"].dt.date
    df["time"] = df["time_input"].dt.time
    df["cycle_start_time"] = df["time_input"] - pd.to_timedelta(df["time_taken"], unit="s")

    # Given ideal cycle time
    ideal_cycle_time = df["cycle_time"].loc[0]  # seconds

    df["downtime"] = (df["time_input"].diff().dt.total_seconds() - df["cycle_time"]).shift(-1)

    # Fill NaN downtime (last row) with 0
    df["downtime"] = df["downtime"].fillna(0)
    tolerance = ideal_cycle_time * 0.1
    #filter values outside ±tolerance
    df = df[df['downtime'].abs() > tolerance]
    return df

def update_sql(mp_id, complete = False):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
    # db_connection_str = 'mysql+pymysql://admin:UL1131@192.168.1.17/machine_monitoring'
    connection = create_engine(db_connection_str).raw_connection()
    with connection.cursor() as cursor:
        information = calculate_downtime(mp_id)
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

