#!/usr/bin/with-contenv bashio

# Get configuration
SERIAL_PORT=$(bashio::config 'serial_port')
TCP_PORT=$(bashio::config 'tcp_port')
LOG_LEVEL=$(bashio::config 'log_level')
MQTT_DISCOVERY_PREFIX=$(bashio::config 'mqtt.discovery_prefix')
MQTT_PREFIX=$(bashio::config 'mqtt.prefix')
MQTT_CLIENT_ID=$(bashio::config 'mqtt.client_id')

# Determine EnOcean connection
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

# Export environment variables
export ENOCEAN_PORT="${ENOCEAN_PORT}"
export LOG_LEVEL="${LOG_LEVEL}"
export MQTT_HOST=$(bashio::services mqtt "host")
export MQTT_PORT=$(bashio::services mqtt "port")
export MQTT_USER=$(bashio::services mqtt "username")
export MQTT_PASSWORD=$(bashio::services mqtt "password")
export MQTT_DISCOVERY_PREFIX="${MQTT_DISCOVERY_PREFIX}"
export MQTT_PREFIX="${MQTT_PREFIX}"
export MQTT_CLIENT_ID="${MQTT_CLIENT_ID}"
export CONFIG_PATH="/config/enocean"

# Create config directory if it doesn't exist
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
