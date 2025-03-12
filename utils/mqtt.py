import threading
import time
import paho.mqtt.client as mqtt
from config.config import MQTT_CONFIG,DB_CONFIG
import json
from sqlalchemy import create_engine, text
from utils.efficiency import update_sql
import time
db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
db_connection = create_engine(db_connection_str)


# ✅ Global variables (Singleton pattern)
mqttc = None
mqtt_thread = None
mqtt_lock = threading.Lock()
mqtt_running = False

mqtt_broker = MQTT_CONFIG["mqtt_broker"]
mqtt_port = MQTT_CONFIG["mqtt_port"]
mqtt_topics = ["status/+", "machine/+", "action/+", "overide/+"]

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("✅ Connected to MQTT broker!")
        for topic in mqtt_topics:
            client.subscribe(topic, qos=2)
            print(f"🔄 Subscribed to {topic}")
    else:
        print(f"❌ Connection failed with reason code {reason_code}")

# def on_disconnect(client, userdata, reason_code, properties=None):
#     print("❌ Disconnected from MQTT broker.")
#     if reason_code != 0:
#         print("⚠️ Unexpected disconnection. Reconnecting...")
#         reconnect_mqtt(client)

def on_disconnect(client, userdata, reason_code, properties=None):
    print(f"❌ Disconnected from MQTT broker. Reason: {reason_code}")
    if reason_code != 0:
        print("⚠️ Unexpected disconnection. Attempting to reconnect...")
        try:
            client.reconnect()
        except Exception as e:
            print(f"⚠️ Reconnect failed: {e}")



# def on_message(client, userdata, msg):
#     try:
#         payload = msg.payload.decode()
#         print(f"📩 Received MQTT message: {msg.topic} - {payload}")
#     except Exception as e:
#         print(f"⚠️ Error processing message: {e}")

def on_message(client, userdata, msg):
    """Callback for handling received messages."""
    try:
        # print(f"Received message on topic: {msg.topic}")
        

        # Decode the message payload
        payload = msg.payload.decode()
        # print(payload)

        print(f"Received MQTT message: {msg.topic} - {payload} - MID: {msg.mid}")


        if msg.topic.startswith("status/"):
            # Handle status update
            message_data = json.loads(payload)
            status = message_data.get("status")
            machine_id = message_data.get("machineid")
            mqtt_machine = f"machines/{machine_id}"
            # if status = disconnected, insert a row into monitoring, saying esp32 disconnected
            if status and machine_id:
                connection = create_engine(db_connection_str).raw_connection()
                with connection.cursor() as cursor:
                    sql = "UPDATE machine_list SET esp_status = %s WHERE machine_code = %s"
                    cursor.execute(sql, (status, machine_id))
                    connection.commit()

                    sql_status = "SELECT machine_status FROM machine_list WHERE machine_code = %s"
                    cursor.execute(sql_status, (machine_id,))
                    result_status = cursor.fetchone()

                    if result_status:
                        machine_status = result_status[0]
                        if machine_status == "mass prod":
                            sql_select = """
                            SELECT main_id
                            FROM joblist
                            WHERE machine_code = %s
                            ORDER BY main_id DESC
                            LIMIT 1
                            """
                            cursor.execute(sql_select, (str(machine_id),))
                            result_mainid = cursor.fetchone()
                            main_id = result_mainid[0] if result_mainid else None

                            sql_select = """
                            SELECT mp_id
                            FROM mass_production
                            WHERE machine_code = %s
                            ORDER BY mp_id DESC
                            LIMIT 1
                            """
                            cursor.execute(sql_select, (str(machine_id),))
                            result_mpid = cursor.fetchone()
                            mp_id = result_mpid[0] if result_mpid else None

                            if main_id and mp_id:
                                message = {
                                    "command": "true",
                                    "mp_id": str(mp_id),
                                    "main_id": str(main_id)
                                }
                                client.publish(mqtt_machine, payload=json.dumps(message))

                    print(f"Updated status for {machine_id} to {status}")

        elif msg.topic.startswith("action/"):
            if msg.topic == "action/job_end":
                message_data = json.loads(payload)
                mp_id = message_data.get("mp_id")
                # print(mp_id)

                update_sql(mp_id, complete=True)

                connection = create_engine(db_connection_str).raw_connection()
                with connection.cursor() as cursor:
                    sql_row_count = """
                    SELECT mp_id, COUNT(*) AS row_count 
                    FROM monitoring 
                    WHERE mp_id = %s
                    GROUP BY mp_id;
                    """

                    cursor.execute(sql_row_count, (mp_id,))  # No need to convert mp_id to string
                    results = cursor.fetchall()

                    for row in results:
                        row_count = row[1]  # COUNT(*), which is an integer

                    sql = """            
                    SELECT 
                    m.mp_id, 
                    mm.mould_code,
                    mm.total_shot_count,
                    mm.next_service_shot_count,
                    COUNT(*) AS row_count
                    FROM monitoring AS m
                    JOIN joblist AS j ON m.main_id = j.main_id
                    JOIN mould_list AS mm ON j.mould_code = mm.mould_code
                    WHERE m.mp_id = %s
                    GROUP BY m.mp_id, mm.mould_code, mm.total_shot_count, mm.next_service_shot_count;
                    """
                    cursor.execute(sql, (mp_id,))  # No need to convert mp_id to string
                    results = cursor.fetchall()
                    print(results) 
                    #848
                    for row in results:
                        mould_code = row[1]  
                        tsc = row[2]  # total_shot_count
                        nssc = row[3]  # next_service_shot_count
                        # row_count = row[4]  # COUNT(*), which is an integer

                        # Add row_count before comparing
                        tsc += row_count
                        if tsc >= nssc:
                            sql_update = """
                            UPDATE mould_list 
                            SET total_shot_count = total_shot_count + %s, service_status = 1 
                            WHERE mould_code = %s
                            """
                        else:
                            sql_update = """
                            UPDATE mould_list 
                            SET total_shot_count = total_shot_count + %s 
                            WHERE mould_code = %s
                            """

                        cursor.execute(sql_update, (row_count, mould_code))  # Use integer for row_count
                        connection.commit()
                        
                    print("job complete")  
                    
            if msg.topic == "action/get_mpid":
                message_data = json.loads(payload)  # Parse JSON
                machine_id = message_data.get("machine_id")  # Correct key name
                mqtt_machine = f"machines/{machine_id}"

                try:
                    with db_connection.connect() as connection:
                        with connection.begin():  # Ensures transaction handling
                            sql = text("""
                                UPDATE machine_list 
                                SET machine_status = 'mass prod'
                                WHERE machine_code = :machine_code
                            """)
                            connection.execute(sql, {"machine_code": machine_id})  # Safe parameter passing

                            sql_query = text("""
                                SELECT mould_id FROM machine_list 
                                WHERE machine_code = :machine_code
                            """)
                            result = connection.execute(sql_query, {"machine_code": machine_id}).fetchone()
                            
                            mould_id = result[0] if result else None  # Handle None case
                            
                            if mould_id is not None:
                                # print(mould_id)
                                
                                sql_insert = text("""
                                    INSERT INTO mass_production (machine_code, mould_id) 
                                    VALUES (:machine_code, :mould_id)
                                """)
                                cursor = connection.execute(sql_insert, {"machine_code": machine_id, "mould_id": mould_id})
                                last_inserted_id = cursor.lastrowid  # Get last inserted ID

                                sql_select = text("""
                                    SELECT main_id FROM joblist
                                    WHERE machine_code = :machine_code
                                    ORDER BY main_id DESC
                                    LIMIT 1
                                """)
                                result = connection.execute(sql_select, {"machine_code": machine_id}).fetchone()

                                main_id = result[0] if result else None  # Handle None case

                                if main_id is not None:
                                    message = {
                                        "command": "start",
                                        "main_id": str(main_id),
                                        "mp_id": last_inserted_id
                                    }
                                    mqttc.publish(mqtt_machine, payload=json.dumps(message))  # Ensure mqttc is correctly initialized

                except Exception as e:
                    print(f"Error updating database: {e}")


            connection.commit() 
                #query 
        elif msg.topic.startswith("machine/cycle_time"):
            message_data = json.loads(payload)
            mp_id = message_data.get("mp_id")
            # print(mp_id)
            update_sql(mp_id)
        
        elif msg.topic.startswith("overide/"):
            message_data = json.loads(payload)  # Parse JSON
            machine_id = message_data.get("machine_id")  # Correct key name
            mqtt_machine = f"machines/{machine_id}"
            try:
                connection = create_engine(db_connection_str).raw_connection()
                with connection.cursor() as cursor:
                    sql = """
                    UPDATE machine_list 
                    SET machine_status = 'active mould not running'
                    WHERE machine_code = %s
                    """
                    cursor.execute(sql, (str(machine_id),))
                    connection.commit()

                    message = {"command": "stop", }
                    mqttc.publish(mqtt_machine, payload=json.dumps(message))
            except Exception as e:
                print(f"Error updating database: {e}")
            finally:
                connection.close()



    except Exception as e:
        print(f"Error processing message: {e}")




# ✅ Reconnect Logic
def reconnect_mqtt(client):
    retry_interval = 5
    while True:
        try:
            client.reconnect()
            print("✅ Reconnected to MQTT broker!")
            break
        except Exception as e:
            print(f"❌ Reconnection failed: {e}. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, 60)

# ✅ Get or Create MQTT Client (Singleton)
def get_mqtt_client():
    global mqttc, mqtt_running, mqtt_thread
    with mqtt_lock:  
        if mqttc is None:
            print("🚀 Creating a new MQTT Client...")
            mqttc = mqtt.Client(client_id="DashMQTTClient", clean_session=False)
            # mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)


            mqttc.on_connect = on_connect
            mqttc.on_disconnect = on_disconnect
            mqttc.on_message = on_message

        if not mqtt_running:
            print(f"🔄 Connecting to MQTT Broker {mqtt_broker}:{mqtt_port} ...")
            mqttc.connect(mqtt_broker, mqtt_port, 60)
            mqttc.loop_forever()
            mqtt_running = True
        else:
            print("⚠️ MQTT is already running! Skipping new connection.")

        return mqttc

# ✅ Ensure MQTT starts once
def start_mqtt():
    global mqtt_thread
    if mqtt_thread is None or not mqtt_thread.is_alive():
        mqtt_thread = threading.Thread(target=get_mqtt_client, daemon=True)
        mqtt_thread.start()




def publish_message(topic, payload, qos=2):
    global mqttc
    for _ in range(3):  # Retry mechanism
        if mqttc and mqttc.is_connected():
            mqttc.publish(topic, payload, qos)
            print(f"📤 Published to {topic}: {payload}")
            return
        else:
            print("❌ MQTT client not connected. Retrying in 2s...")
            time.sleep(2)
