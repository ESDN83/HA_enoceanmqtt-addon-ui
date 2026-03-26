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

# Export environment variables
export ENOCEAN_PORT="${ENOCEAN_PORT}"
export LOG_LEVEL="${LOG_LEVEL}"
export CACHE_DEVICE_STATES="${CACHE_DEVICE_STATES}"
export MQTT_HOST=$(bashio::services mqtt "host")
export MQTT_PORT=$(bashio::services mqtt "port")
export MQTT_USER=$(bashio::services mqtt "username")
export MQTT_PASSWORD=$(bashio::services mqtt "password")
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
