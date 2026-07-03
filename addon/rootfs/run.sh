#!/usr/bin/with-contenv bashio

# Get configuration
SERIAL_PORT=$(bashio::config 'serial_port')
TCP_PORT=$(bashio::config 'tcp_port')
LOG_LEVEL=$(bashio::config 'log_level')
CACHE_DEVICE_STATES=$(bashio::config 'cache_device_states')
MQTT_DISCOVERY_PREFIX=$(bashio::config 'mqtt.discovery_prefix')
MQTT_PREFIX=$(bashio::config 'mqtt.prefix')
MQTT_CLIENT_ID=$(bashio::config 'mqtt.client_id')

# Determine EnOcean connection: TCP takes priority over serial
if bashio::var.has_value "${TCP_PORT}"; then
    ENOCEAN_PORT="${TCP_PORT}"
    bashio::log.info "Using TCP EnOcean connection: ${ENOCEAN_PORT}"
elif bashio::var.has_value "${SERIAL_PORT}"; then
    ENOCEAN_PORT="${SERIAL_PORT}"
    bashio::log.info "Using Serial EnOcean connection: ${ENOCEAN_PORT}"
else
    bashio::log.warning "No EnOcean port configured - running in UI-only mode"
    ENOCEAN_PORT=""
fi

# Data path: /data/ is the correct persistent storage for HA addons
# It survives addon updates (unlike /config/enocean which was wrong)
CONFIG_PATH="/data"

# One-time migration from old config path (/config/enocean → /data/)
# Uses marker file in /config/ (survives addon uninstall) to prevent re-migration
if [ -d "/config/enocean" ] && [ ! -f "/config/.enocean_migrated" ]; then
    bashio::log.info "Migrating configuration from /config/enocean to ${CONFIG_PATH}/"
    cp -a /config/enocean/* "${CONFIG_PATH}/" 2>/dev/null || true
    # Mark migration as done (in /config/ so it survives addon reinstall)
    touch /config/.enocean_migrated
    bashio::log.info "Migration complete"
fi

# MQTT broker selection:
#   - If a host is set under the mqtt.* options, use that external broker
#     (e.g. a standalone Mosquitto container on UNRAID). Port/user/password
#     come from the options too, with a 1883 default.
#   - Otherwise fall back to the broker provided by the Home Assistant MQTT
#     service (the Mosquitto add-on), auto-discovered via bashio.
MQTT_HOST_OPT=$(bashio::config 'mqtt.host')

if bashio::var.has_value "${MQTT_HOST_OPT}"; then
    MQTT_HOST="${MQTT_HOST_OPT}"
    MQTT_PORT=$(bashio::config 'mqtt.port')
    MQTT_USER=$(bashio::config 'mqtt.username')
    MQTT_PASSWORD=$(bashio::config 'mqtt.password')
    bashio::var.has_value "${MQTT_PORT}" || MQTT_PORT="1883"
    bashio::log.info "Using external MQTT broker: ${MQTT_HOST}:${MQTT_PORT}"
elif bashio::services.available "mqtt"; then
    MQTT_HOST=$(bashio::services mqtt "host")
    MQTT_PORT=$(bashio::services mqtt "port")
    MQTT_USER=$(bashio::services mqtt "username")
    MQTT_PASSWORD=$(bashio::services mqtt "password")
    bashio::log.info "Using Home Assistant MQTT service: ${MQTT_HOST}:${MQTT_PORT}"
else
    bashio::log.error "No MQTT broker available: set mqtt.host in the add-on"
    bashio::log.error "options, or install/configure the Mosquitto broker add-on."
    MQTT_HOST=""
    MQTT_PORT="1883"
    MQTT_USER=""
    MQTT_PASSWORD=""
fi

# Export environment variables
export ENOCEAN_PORT="${ENOCEAN_PORT}"
export LOG_LEVEL="${LOG_LEVEL}"
export CACHE_DEVICE_STATES="${CACHE_DEVICE_STATES}"
export MQTT_HOST="${MQTT_HOST}"
export MQTT_PORT="${MQTT_PORT}"
export MQTT_USER="${MQTT_USER}"
export MQTT_PASSWORD="${MQTT_PASSWORD}"
export MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
export MQTT_PREFIX="${MQTT_PREFIX}"
export MQTT_CLIENT_ID="${MQTT_CLIENT_ID}"
export CONFIG_PATH="${CONFIG_PATH}"

# Create data directories if they don't exist
mkdir -p "${CONFIG_PATH}"
mkdir -p "${CONFIG_PATH}/custom_eep"

# Log startup
bashio::log.info "Starting EnOcean MQTT..."
bashio::log.info "EnOcean Port: ${ENOCEAN_PORT:-not configured}"
bashio::log.info "Log Level: ${LOG_LEVEL}"
bashio::log.info "MQTT Broker: ${MQTT_HOST}:${MQTT_PORT}"
bashio::log.info "MQTT Prefix: ${MQTT_PREFIX}"
bashio::log.info "Config Path: ${CONFIG_PATH}"

# Start the application
cd /app
exec python3 main.py
