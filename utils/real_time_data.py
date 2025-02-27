import pandas as pd
from sqlalchemy import create_engine
from config.config import DB_CONFIG


def get_running_machines():
    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    connection = create_engine(db_connection_str).raw_connection()
    cursor = connection.cursor()
    # Query the database
    query = f"""
        SELECT 
        mp.mp_id
        FROM mass_production AS mp
        JOIN machine_list AS ml ON ml.machine_code = mp.machine_code
        WHERE ml.machine_status = "mass prod"
        AND mp.mp_id = (
            SELECT MAX(mp_id) 
            FROM mass_production 
            WHERE machine_code = mp.machine_code
        );
    """
    cursor.execute(query)
    result = cursor.fetchall()

    mp_ids = [row[0] for row in result]  # Extract all values

    return mp_ids
    




def calculate_downtime(mp_id):
    # Ensure mp_id is always a list
    if not isinstance(mp_id, list):
        mp_id = [mp_id]

    # Connect to the database
    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    db_engine = create_engine(db_connection_str)

    # Generate a dynamic placeholder string for multiple values
    placeholders = ", ".join(["%s"] * len(mp_id))

    # Correct SQL query using `%s` for parameter substitution
    query = f"""
    SELECT m.*, j.mould_code, mm.cycle_time 
    FROM monitoring AS m
    JOIN joblist AS j ON m.main_id = j.main_id
    JOIN mould_masterlist AS mm ON j.mould_code = mm.mould_code
    WHERE m.mp_id IN ({placeholders})
    ORDER BY m.time_input;
    """

    # Fetch data using `pd.read_sql()` with tuple parameters
    df = pd.read_sql(query, con=db_engine, params=tuple(mp_id))

    # Ensure the dataframe is not empty
    if df.empty:
        print(f"No data found for mp_id: {mp_id}")
        return {"production_time": 0, "ideal_time": 0, "downtime": 0, "efficiency": 0}

    df["time_input"] = pd.to_datetime(df["time_input"])
    df["date"] = df["time_input"].dt.date
    df["time"] = df["time_input"].dt.time
    df["cycle_start_time"] = df["time_input"] - pd.to_timedelta(df["time_taken"], unit="s")

    # Given ideal cycle time
    ideal_cycle_time = df["cycle_time"].iloc[0]  # Use .iloc[0] to avoid errors

    # Calculate Downtime: (Cycle Start Time of next cycle - Time Input of current cycle) - Ideal Cycle Time
    df["downtime"] = df["cycle_start_time"].shift(-1) - df["time_input"]
    df["downtime"] = df["downtime"].dt.total_seconds() - ideal_cycle_time  # Convert to seconds

    # Fill NaN downtime (last row) with 0
    df["downtime"] = df["downtime"].fillna(0)

    # Print results for debugging
    print(f"Processed mp_id: {mp_id}")
    print(df)

    # Compute total values
    total_ideal_time = len(df.index) * ideal_cycle_time
    total_downtime = df['downtime'].sum()
    total_production_time = df['time_taken'].sum()

    # Prevent division by zero
    if total_production_time + total_downtime == 0:
        efficiency = 0
    else:
        efficiency = (total_ideal_time / (total_production_time + total_downtime)) * 100

    return {
        "production_time": total_production_time,
        "ideal_time": total_ideal_time,
        "downtime": total_downtime,
        "efficiency": efficiency
    }

def update_sql_real_time(mp_id):
    if not isinstance(mp_id, list):  # Ensure it's a list
        mp_id = [mp_id]

    for ids in mp_id: 
        print(ids)

    db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    db_connection = create_engine(db_connection_str)
    connection = db_connection.raw_connection()  # Use the same connection object

    with connection.cursor() as cursor:
        for ids in mp_id: 
            information = calculate_downtime(ids)

            sql_update = """
            UPDATE mass_production 
            SET total_production_time = %s, downtime = %s, efficiency = %s 
            WHERE mp_id = %s
            """
            # Pass 'ids' instead of 'mp_id'
            cursor.execute(sql_update, (information["production_time"], information["downtime"], information["efficiency"], ids))
        
        connection.commit()  # Commit once after all updates




# update_sql(get_running_machines())