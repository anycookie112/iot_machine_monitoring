from airflow.decorators import dag, task
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import requests
import json

ip = "192.168.5.38"

DB_CONFIG = {
    "username": "root",
    "password": "UL1131",
    "host": "192.168.5.31",
    "database": "machine_monitoring"
}

@dag(
    dag_id="iot_monitoring",
    schedule="*/15 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    dagrun_timeout=timedelta(minutes=30),
)
def extract_data():

    @task
    def test_connection():
        engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("DB OK:", result.fetchone())

    @task
    def test_connection_esp():
        try:
            response = requests.get(f"http://{ip}/ping", timeout=3)
            return response.status_code == 200
        except Exception as e:
            print("ESP Error:", e)
            return False

    @task
    def get_log():
        response = requests.get(f"http://{ip}/log", timeout=10)
        return response.text

    @task
    def transform(raw_data):
        action_map = {0: "normal_cycle", 1: "downtime", 2: "abnormal_cycle"}
        values = [v.strip() for v in raw_data.strip().split(',') if v.strip()]
        records = []
        for i in range(0, len(values) - 4, 5):
            try:
                records.append({
                    "timestamp": values[i],
                    "elapsed_time": float(values[i + 1]),
                    "main_id": int(values[i + 2]),
                    "mp_id": int(values[i + 3]),
                    "action": action_map.get(int(values[i + 4]), "unknown")
                })
            except Exception as e:
                print(f"Skipping bad row at {i}: {e}")
        return records

    @task
    def batch_save_to_db(data):
        engine = create_engine(f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")
        insert = text("INSERT INTO monitoring (main_id, mp_id, action, time_taken, time_input) VALUES (:main_id, :mp_id, :action, :time_taken, :time_input)")
        with engine.begin() as conn:
            for row in data:
                conn.execute(insert, {
                "main_id": row["main_id"],
                "mp_id": row["mp_id"],
                "action": row["action"],
                "time_taken": row["elapsed_time"],
                "time_input": row["timestamp"]  
            })


    @task(retries=10, retry_delay=timedelta(seconds=10))
    def clear_logs():
        requests.post(f"http://{ip}/clear_log", timeout=5)

    # DAG flow
    db_ok = test_connection()
    esp_ok = test_connection_esp()
    raw = get_log()
    parsed = transform(raw)
    saved = batch_save_to_db(parsed)
    saved >> clear_logs()

dag = extract_data()
