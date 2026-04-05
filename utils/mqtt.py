from sqlalchemy import create_engine, text
import paho.mqtt.client as mqtt
import json
import threading
import time
from utils.efficiency import update_sql
from config.config import MQTT_CONFIG, DB_CONFIG

db_connection_str = f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
db_connection = create_engine(db_connection_str)

#  MQTT Configuration
mqtt_broker = MQTT_CONFIG["mqtt_broker"]
mqtt_port = MQTT_CONFIG["mqtt_port"]
mqtt_topics = ["status/+", "machine/+", "action/+", "overide/+"]

#  Global Variables (Singleton Pattern)
mqttc = None  # Client object
mqtt_running = False  # Ensure MQTT starts only once
mqtt_lock = threading.Lock()  # Prevent race conditions


def update_machine_esp_status(machine_id, status):
    if not machine_id:
        return

    try:
        with db_connection.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE machine_list
                    SET esp_status = :status
                    WHERE machine_code = :machine_code
                    """
                ),
                {"status": status, "machine_code": machine_id},
            )
    except Exception as e:
        print(f"[ERROR] Failed to update esp_status for {machine_id}: {e}")


#  MQTT Callbacks
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(" Connected to MQTT broker!")
        for topic in mqtt_topics:
            client.subscribe(topic, qos=2)
            print(f" Subscribed to {topic}")
    else:
        print(f" Connection failed with reason code {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    print(" Disconnected from MQTT broker.")
    if reason_code != 0:
        print(" Unexpected disconnection. Reconnecting...")
        reconnect_mqtt(client)

def on_message(client, userdata, msg):
    """Callback for handling received messages."""
    try:
        # print(f"Received message on topic: {msg.topic}")
        

        # Decode the message payload
        payload = msg.payload.decode()
        # print(payload)

        print(f"Received MQTT message: {msg.topic} - {payload} - MID: {msg.mid}")


        if msg.topic.startswith("status/"):
            try:
                # Parse incoming MQTT payload
                message_data = json.loads(payload)
                status = message_data.get("status")
                machine_id = message_data.get("machineid")
                mqtt_machine = f"machines/{machine_id}"

                if status and machine_id:
                    update_machine_esp_status(machine_id, status)
                    connection = create_engine(db_connection_str).raw_connection()
                    try:
                        with connection.cursor() as cursor:
                            # If disconnected, log error
                            if status == "disconnected":
                                sql_logging = """
                                    INSERT INTO error_logs (machine_code, error_type, time_input)
                                    VALUES (%s, %s, NOW())
                                """
                                cursor.execute(sql_logging, (machine_id, "ESP Disconnected"))
                                connection.commit()

                            # Fetch current machine status from DB
                            sql_status = """
                                SELECT machine_status
                                FROM machine_list
                                WHERE machine_code = %s
                            """
                            cursor.execute(sql_status, (machine_id,))
                            result_status = cursor.fetchone()

                            if result_status:
                                machine_status = result_status[0].strip().lower()

                                command_message = None

                                if machine_status == "mass prod":
                                    # Fetch latest main_id
                                    cursor.execute("""
                                        SELECT main_id
                                        FROM joblist
                                        WHERE machine_code = %s
                                        ORDER BY main_id DESC
                                        LIMIT 1
                                    """, (machine_id,))
                                    result_mainid = cursor.fetchone()
                                    main_id = result_mainid[0] if result_mainid else None

                                    # Fetch latest mp_id
                                    cursor.execute("""
                                        SELECT mp_id
                                        FROM mass_production
                                        WHERE machine_code = %s
                                        ORDER BY mp_id DESC
                                        LIMIT 1
                                    """, (machine_id,))
                                    result_mpid = cursor.fetchone()
                                    mp_id = result_mpid[0] if result_mpid else None

                                    if main_id and mp_id:
                                        command_message = {
                                            "command": "true",
                                            "mp_id": str(mp_id),
                                            "main_id": str(main_id)
                                        }
                                        print(f"[DEBUG] {machine_id} mass prod → Sending TRUE with mp_id={mp_id}, main_id={main_id}")
                                    else:
                                        print(f"[DEBUG] {machine_id} mass prod → Missing mp_id/main_id, not sending")

                                elif machine_status in ("change mould in progress", "adjustment/qa in progress"):
                                    command_message = {"command": "qas"}
                                    print(f"[DEBUG] {machine_id} change mould/QA → Sending QAS")

                                elif machine_status == "active mould not running":
                                    command_message = {"command": "qae"}
                                    print(f"[DEBUG] {machine_id} mould not running → Sending QAE")

                                else:
                                    print(f"[DEBUG] {machine_id} has unhandled status '{machine_status}' → No command sent")

                                # Publish the decided command
                                if command_message:
                                    client.publish(mqtt_machine, payload=json.dumps(command_message))
                    finally:
                        connection.close()

                    print(f"Updated status for {machine_id} to {status}")

            except Exception as e:
                print(f"[ERROR] Exception in status handler: {e}")


        elif msg.topic.startswith("action/"):
            if msg.topic == "action/job_end":
                message_data = json.loads(payload)
                mp_id = message_data.get("mp_id")
                # print(mp_id)

                if not mp_id:
                    return

                update_sql(mp_id, complete=True)

                connection = create_engine(db_connection_str).raw_connection()
                try:
                    with connection.cursor() as cursor:
                        sql_row_count = """
                        SELECT mp_id, COUNT(*) AS row_count 
                        FROM monitoring 
                        WHERE mp_id = %s
                        GROUP BY mp_id;
                        """

                        cursor.execute(sql_row_count, (mp_id,))
                        results = cursor.fetchall()
                        row_count = results[0][1] if results else 0

                        if row_count == 0:
                            return

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
                        cursor.execute(sql, (mp_id,))
                        results = cursor.fetchall()
                        for row in results:
                            mould_code = row[1]
                            tsc = row[2]
                            nssc = row[3]

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

                            cursor.execute(sql_update, (row_count, mould_code))
                            connection.commit()

                        print("job complete")
                finally:
                    connection.close()
                    
            if msg.topic == "action/get_mpid":
                message_data = json.loads(payload)  # Parse JSON
                machine_id = message_data.get("machine_id")  # Correct key name
                mqtt_machine = f"machines/{machine_id}"
                update_machine_esp_status(machine_id, "connected")

                try:
                    with db_connection.connect() as connection:
                        with connection.begin():  # Ensures transaction handling
                            
                            sql_query = text("""
                                SELECT mould_id, machine_status 
                                FROM machine_list 
                                WHERE machine_code = :machine_code
                            """)
                            result = connection.execute(sql_query, {"machine_code": machine_id}).fetchone()

                            # Unpack safely with defaults
                            mould_id, machine_status = result if result else (None, None)
                            print({"mould_id": mould_id, "machine_status": machine_status})


                            sql = text("""
                                UPDATE machine_list 
                                SET machine_status = 'mass prod'
                                WHERE machine_code = :machine_code
                            """)
                            connection.execute(sql, {"machine_code": machine_id})  # Safe parameter passing



                            if machine_status == "mass prod":
                                if mould_id is not None:
                                    # print(mould_id)

                                    sql_select = text("""
                                        SELECT main_id, mp_id FROM mass_production
                                        WHERE machine_code = :machine_code
                                        ORDER BY mp_id DESC
                                        LIMIT 1
                                    """)
                                    result = connection.execute(sql_select, {"machine_code": machine_id}).fetchone()

                                    main_id, mp_id = result if result else (None, None)

                                    if main_id is not None:
                                        message = {
                                            "command": "start",
                                            "main_id": str(main_id),
                                            "mp_id": str(mp_id)
                                        }
                                        mqttc.publish(mqtt_machine, payload=json.dumps(message))  # Ensure mqttc is correctly initialized
                            if machine_status == "active mould not running":
                                if mould_id is not None:
                                    # print(mould_id)

                                    sql_select = text("""
                                        SELECT main_id FROM joblist
                                        WHERE machine_code = :machine_code
                                        ORDER BY main_id DESC
                                        LIMIT 1
                                    """)
                                    result = connection.execute(sql_select, {"machine_code": machine_id}).fetchone()

                                    main_id = result[0] if result else None  # Handle None case

                                    
                                    sql_insert = text("""
                                        INSERT INTO mass_production (machine_code, mould_id, main_id) 
                                        VALUES (:machine_code, :mould_id, :main_id)
                                    """)
                                    cursor = connection.execute(sql_insert, {"machine_code": machine_id, "mould_id": mould_id, "main_id": main_id})
                                    last_inserted_id = cursor.lastrowid  # Get last inserted ID

                                    if main_id is not None:
                                        message = {
                                            "command": "start",
                                            "main_id": str(main_id),
                                            "mp_id": last_inserted_id
                                        }
                                        mqttc.publish(mqtt_machine, payload=json.dumps(message))  # Ensure mqttc is correctly initialized





                except Exception as e:
                    print(f"Error updating database: {e}")


        elif msg.topic.startswith("machine/cycle_time"):
            message_data = json.loads(payload)
            mp_id = message_data.get("mp_id")
            machine_id = message_data.get("machineid")
            update_machine_esp_status(machine_id, "connected")
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

def reconnect_mqtt(client):
    retry_interval = 5
    while True:
        try:
            client.reconnect()
            print(" Reconnected to MQTT broker!")
            break
        except Exception as e:
            print(f" Reconnection failed: {e}. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, 60)

#  Publish function
def publish_message(topic, payload, qos=2):
    global mqttc
    if mqttc and mqttc.is_connected():
        mqttc.publish(topic, payload, qos)
        print(f" Published to {topic}: {payload}")
    else:
        print(" MQTT client is not connected. Cannot publish message.")

#  Singleton MQTT Initialization
def get_mqtt_client():
    global mqttc, mqtt_running
    with mqtt_lock:  # Ensure thread safety
        if mqttc is None:
            print("🔄 Initializing MQTT client...")
            mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)

            # Assign Callbacks
            mqttc.on_connect = on_connect
            mqttc.on_disconnect = on_disconnect
            mqttc.on_message = on_message

        if not mqtt_running:
            print(f"🔄 Connecting to MQTT Broker {mqtt_broker}:{mqtt_port} ...")
            mqttc.connect(mqtt_broker, mqtt_port, 60)
            mqttc.loop_start()
            mqtt_running = True  # Prevent multiple connections
        return mqttc  # Return the same instance always
