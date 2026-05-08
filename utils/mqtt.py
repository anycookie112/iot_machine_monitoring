import json
import logging
import threading
import time
from contextlib import closing

import paho.mqtt.client as mqtt
import paho.mqtt.publish as mqtt_publish
from sqlalchemy import text

from config.config import MQTT_CONFIG
from utils.db import get_db_engine, get_raw_connection
from utils.efficiency import update_sql


logger = logging.getLogger(__name__)

mqtt_topics = ["status/+", "machine/+", "action/+", "overide/+"]

_consumer_client = None
_consumer_lock = threading.Lock()


def _publish_from_consumer(client, topic, payload, qos=2):
    client.publish(topic, payload=json.dumps(payload), qos=qos)
    logger.info("Published MQTT response to %s: %s", topic, payload)


def update_machine_esp_status(machine_id, status):
    if not machine_id:
        return

    try:
        with get_db_engine().begin() as connection:
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
    except Exception:
        logger.exception("Failed to update esp_status for %s", machine_id)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        logger.error("MQTT connection failed with reason code %s", reason_code)
        return

    logger.info(
        "Connected to MQTT broker at %s:%s",
        MQTT_CONFIG["mqtt_broker"],
        MQTT_CONFIG["mqtt_port"],
    )
    for topic in mqtt_topics:
        client.subscribe(topic, qos=2)
        logger.info("Subscribed to %s", topic)


def on_disconnect(client, userdata, flags, reason_code, properties):
    logger.warning("Disconnected from MQTT broker with reason code %s", reason_code)
    if reason_code != 0:
        reconnect_mqtt(client)


def _handle_status_message(client, payload):
    message_data = json.loads(payload)
    status = message_data.get("status")
    machine_id = message_data.get("machineid")
    mqtt_machine = f"machines/{machine_id}"

    if not status or not machine_id:
        return

    update_machine_esp_status(machine_id, status)

    with closing(get_raw_connection()) as connection:
        with connection.cursor() as cursor:
            if status == "disconnected":
                cursor.execute(
                    """
                    INSERT INTO error_logs (machine_code, error_type, time_input)
                    VALUES (%s, %s, NOW())
                    """,
                    (machine_id, "ESP Disconnected"),
                )
                connection.commit()

            cursor.execute(
                """
                SELECT machine_status
                FROM machine_list
                WHERE machine_code = %s
                """,
                (machine_id,),
            )
            result_status = cursor.fetchone()

            if not result_status:
                return

            machine_status = (result_status[0] or "").strip().lower()
            command_message = None

            if machine_status == "mass prod":
                cursor.execute(
                    """
                    SELECT main_id, mp_id
                    FROM mass_production
                    WHERE machine_code = %s
                    ORDER BY mp_id DESC
                    LIMIT 1
                    """,
                    (machine_id,),
                )
                result_resume = cursor.fetchone()
                if result_resume:
                    main_id, mp_id = result_resume
                else:
                    main_id, mp_id = (None, None)

                if main_id and mp_id:
                    command_message = {
                        "command": "true",
                        "mp_id": str(mp_id),
                        "main_id": str(main_id),
                    }
                else:
                    logger.warning(
                        "Machine %s is in mass prod without main_id/mp_id; skipping resume publish",
                        machine_id,
                    )

            elif machine_status in ("change mould in progress", "adjustment/qa in progress"):
                command_message = {"command": "qas"}
            elif machine_status == "active mould not running":
                command_message = {"command": "qae"}

            if command_message:
                _publish_from_consumer(client, mqtt_machine, command_message)


def _handle_job_end(payload):
    message_data = json.loads(payload)
    mp_id = message_data.get("mp_id")

    if not mp_id:
        return

    update_sql(mp_id, complete=True)

    with closing(get_raw_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT mp_id, COUNT(*) AS row_count
                FROM monitoring
                WHERE mp_id = %s
                GROUP BY mp_id
                """,
                (mp_id,),
            )
            results = cursor.fetchall()
            row_count = results[0][1] if results else 0

            if row_count == 0:
                return

            cursor.execute(
                """
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
                GROUP BY
                    m.mp_id,
                    mm.mould_code,
                    mm.total_shot_count,
                    mm.next_service_shot_count
                """,
                (mp_id,),
            )
            results = cursor.fetchall()
            for row in results:
                mould_code = row[1]
                total_shot_count = row[2]
                next_service_shot_count = row[3]
                updated_total = total_shot_count + row_count

                if updated_total >= next_service_shot_count:
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

    logger.info("Completed job_end workflow for mp_id=%s", mp_id)


def _handle_get_mpid(client, payload):
    message_data = json.loads(payload)
    machine_id = message_data.get("machine_id")
    mqtt_machine = f"machines/{machine_id}"
    update_machine_esp_status(machine_id, "connected")

    if not machine_id:
        return

    try:
        with get_db_engine().begin() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT mould_id, machine_status
                    FROM machine_list
                    WHERE machine_code = :machine_code
                    """
                ),
                {"machine_code": machine_id},
            ).fetchone()

            mould_id, machine_status = result if result else (None, None)

            connection.execute(
                text(
                    """
                    UPDATE machine_list
                    SET machine_status = 'mass prod'
                    WHERE machine_code = :machine_code
                    """
                ),
                {"machine_code": machine_id},
            )

            if machine_status == "mass prod" and mould_id is not None:
                result = connection.execute(
                    text(
                        """
                        SELECT main_id, mp_id
                        FROM mass_production
                        WHERE machine_code = :machine_code
                        ORDER BY mp_id DESC
                        LIMIT 1
                        """
                    ),
                    {"machine_code": machine_id},
                ).fetchone()

                main_id, mp_id = result if result else (None, None)
                if main_id is not None:
                    _publish_from_consumer(
                        client,
                        mqtt_machine,
                        {"command": "start", "main_id": str(main_id), "mp_id": str(mp_id)},
                    )

            if machine_status == "active mould not running" and mould_id is not None:
                result = connection.execute(
                    text(
                        """
                        SELECT main_id
                        FROM joblist
                        WHERE machine_code = :machine_code
                        ORDER BY main_id DESC
                        LIMIT 1
                        """
                    ),
                    {"machine_code": machine_id},
                ).fetchone()

                main_id = result[0] if result else None
                cursor = connection.execute(
                    text(
                        """
                        INSERT INTO mass_production (machine_code, mould_id, main_id)
                        VALUES (:machine_code, :mould_id, :main_id)
                        """
                    ),
                    {
                        "machine_code": machine_id,
                        "mould_id": mould_id,
                        "main_id": main_id,
                    },
                )
                last_inserted_id = cursor.lastrowid

                if main_id is not None:
                    _publish_from_consumer(
                        client,
                        mqtt_machine,
                        {
                            "command": "start",
                            "main_id": str(main_id),
                            "mp_id": last_inserted_id,
                        },
                    )
    except Exception:
        logger.exception("Error updating machine state after action/get_mpid for %s", machine_id)


def _handle_cycle_time(payload):
    message_data = json.loads(payload)
    mp_id = message_data.get("mp_id")
    main_id = message_data.get("main_id")
    machine_id = message_data.get("machineid")
    action = message_data.get("action")
    update_machine_esp_status(machine_id, "connected")

    try:
        parsed_main_id = int(main_id)
        parsed_mp_id = int(mp_id)
    except (TypeError, ValueError):
        logger.warning(
            "Skipping cycle_time update for %s because main_id/mp_id is invalid: main_id=%r mp_id=%r action=%r",
            machine_id,
            main_id,
            mp_id,
            action,
        )
        return

    if parsed_main_id <= 0 or parsed_mp_id <= 0:
        logger.warning(
            "Skipping cycle_time update for %s because main_id/mp_id is not initialized: main_id=%s mp_id=%s action=%r",
            machine_id,
            parsed_main_id,
            parsed_mp_id,
            action,
        )
        return

    update_sql(parsed_mp_id)


def _handle_override(client, payload):
    message_data = json.loads(payload)
    machine_id = message_data.get("machine_id")
    mqtt_machine = f"machines/{machine_id}"

    if not machine_id:
        return

    try:
        with closing(get_raw_connection()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE machine_list
                    SET machine_status = 'active mould not running'
                    WHERE machine_code = %s
                    """,
                    (str(machine_id),),
                )
                connection.commit()

        _publish_from_consumer(client, mqtt_machine, {"command": "stop"})
    except Exception:
        logger.exception("Error handling override event for %s", machine_id)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        logger.info("Received MQTT message on %s: %s", msg.topic, payload)

        if msg.topic.startswith("status/"):
            _handle_status_message(client, payload)
        elif msg.topic == "action/job_end":
            _handle_job_end(payload)
        elif msg.topic == "action/get_mpid":
            _handle_get_mpid(client, payload)
        elif msg.topic.startswith("machine/cycle_time"):
            _handle_cycle_time(payload)
        elif msg.topic.startswith("overide/"):
            _handle_override(client, payload)
    except Exception:
        logger.exception("Error processing MQTT message on %s", msg.topic)


def reconnect_mqtt(client):
    retry_interval = 5
    while True:
        try:
            client.reconnect()
            logger.info("Reconnected to MQTT broker")
            return
        except Exception:
            logger.exception(
                "MQTT reconnect failed; retrying in %s seconds",
                retry_interval,
            )
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, 60)


def publish_message(topic, payload, qos=2):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)

    try:
        mqtt_publish.single(
            topic,
            payload=payload,
            qos=qos,
            hostname=MQTT_CONFIG["mqtt_broker"],
            port=MQTT_CONFIG["mqtt_port"],
        )
        logger.info("Published MQTT command to %s: %s", topic, payload)
        return True
    except Exception:
        logger.exception("Failed to publish MQTT command to %s", topic)
        return False


def get_mqtt_client():
    global _consumer_client

    with _consumer_lock:
        if _consumer_client is None:
            _consumer_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)
            _consumer_client.on_connect = on_connect
            _consumer_client.on_disconnect = on_disconnect
            _consumer_client.on_message = on_message

        return _consumer_client


def start_mqtt_consumer():
    client = get_mqtt_client()

    while True:
        try:
            logger.info(
                "Starting MQTT consumer against %s:%s",
                MQTT_CONFIG["mqtt_broker"],
                MQTT_CONFIG["mqtt_port"],
            )
            client.connect(MQTT_CONFIG["mqtt_broker"], MQTT_CONFIG["mqtt_port"], 60)
            client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping MQTT consumer")
            raise
        except Exception:
            logger.exception("MQTT consumer crashed; retrying in 5 seconds")
            time.sleep(5)
