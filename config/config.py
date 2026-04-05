import os


DB_CONFIG = {
    "username": os.getenv("MM_DB_USERNAME", "admin"),
    "password": os.getenv("MM_DB_PASSWORD", "UL1131"),
    "host": os.getenv("MM_DB_HOST", "192.168.1.17"),
    "database": os.getenv("MM_DB_NAME", "machine_monitoring"),
}

MQTT_CONFIG = {
    "mqtt_broker": os.getenv("MM_MQTT_BROKER", "192.168.1.17"),
    "mqtt_port": int(os.getenv("MM_MQTT_PORT", "1883")),
}
