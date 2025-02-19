from utils.efficiency import calculate_downtime
import pandas as pd
from sqlalchemy import create_engine


def calculate_downtime(mp_id):
    # Connect to the database
    db_connection_str = 'mysql+pymysql://root:UL1131@localhost/machine_monitoring'
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

    # Calculate Downtime: (Cycle Start Time of next cycle - Time Input of current cycle) - Ideal Cycle Time
    df["downtime"] = (df["time_input"].diff().dt.total_seconds() - df["cycle_time"]).shift(-1)

    # Fill NaN downtime (last row) with 0
    df["downtime"] = df["downtime"].fillna(0)

    # Print results
    # print(df[["mp_id", "time_taken", "time_input", "cycle_start_time", "downtime"]])
    
    total_ideal_time = len(df.index) * ideal_cycle_time
    total_downtime = df['downtime'].sum()
    total_production_time = df['time_taken'].sum()
    efficiency = (total_ideal_time /(total_production_time + total_downtime)) * 100
    # print(total_ideal_time)
    # print(total_production_time)
    # print(efficieccy)
    return df


df = calculate_downtime(46)
# df = df[df["downtime"] >= 5]
df_new = pd.DataFrame(columns=df.columns)  # Create empty DataFrame with same columns

print(df)

