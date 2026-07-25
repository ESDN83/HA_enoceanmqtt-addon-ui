#!/bin/bash
# Create one test device per discovery path and give each a state, so the whole
# UI can be reviewed without a dongle.
#
#   ./fixtures.sh          create devices and seed states
#   ./fixtures.sh clean    delete the TEST_ devices again
#
# Why the states matter: with no dongle nothing ever publishes, entities stay
# "unknown", and Home Assistant then draws two on/off buttons instead of a
# toggle. That looks exactly like the assumed_state bug, so seed states before
# judging any switch rendering.
set -u
cd "$(dirname "$0")" && . ./lib.sh

post() { addon curl -s -X POST localhost:8099/api/devices -H 'Content-Type: application/json' -d "$1" -o /dev/null -w "%{http_code} $2\n"; }

if [ "${1:-}" = "clean" ]; then
  for n in $(addon_api /api/devices | python3 -c "import sys,json;print(' '.join(d['name'] for d in json.load(sys.stdin) if d['name'].startswith('TEST_')))"); do
    addon curl -s -X DELETE "localhost:8099/api/devices/$n" -o /dev/null -w "%{http_code} deleted $n\n"
  done
  exit 0
fi

log "creating fixtures"
post '{"name":"TEST_Light_Eltako","address":"0x05100001","rorg":"A5","func":"38","type":"08","sender_id":"0xFFAAE001","actuator_type":"light","description":"Dimmer Eltako","manufacturer":"Eltako"}'  "light A5-38-08"
post '{"name":"TEST_Switch_Eltako","address":"0x05100002","rorg":"F6","func":"02","type":"01","sender_id":"0xFFAAE002","actuator_type":"switch","description":"Schalter FSR61","manufacturer":"Eltako"}' "switch F6 (FSR61)"
post '{"name":"TEST_Switch_Invert","address":"0x05100003","rorg":"F6","func":"02","type":"01","sender_id":"0xFFAAE003","actuator_type":"switch","invert":true,"description":"Schalter invertiert","manufacturer":"Eltako"}' "switch with invert"
post '{"name":"TEST_Cover_Eltako","address":"0x05100004","rorg":"F6","func":"02","type":"01","sender_id":"0xFFAAE004","actuator_type":"cover","description":"Rollo Eltako","manufacturer":"Eltako"}'   "cover F6"
post '{"name":"TEST_Cover_NodOn","address":"0x05100005","rorg":"D2","func":"05","type":"00","sender_id":"0xFFAAE005","actuator_type":"cover","description":"Rollo NodOn","manufacturer":"NodOn"}'      "cover D2-05 (position)"
post '{"name":"TEST_Sensor_Temp","address":"0x05100006","rorg":"A5","func":"02","type":"05","description":"Temperatursensor","manufacturer":"Generic"}'                                               "sensor A5-02-05"
post '{"name":"TEST_Sensor_Rocker","address":"0x05100007","rorg":"F6","func":"02","type":"01","description":"Taster 4 Tasten","manufacturer":"Generic"}'                                              "sensor F6 (4 buttons)"
post '{"name":"TEST_Chan_CH1","address":"0x05100008","rorg":"D2","func":"01","type":"12","sender_id":"0xFFAAE008","actuator_type":"switch","channel":0,"description":"Wohnzimmer","manufacturer":"NodOn"}' "D2-01-12 channel 1"
post '{"name":"TEST_Chan_CH2","address":"0x05100008","rorg":"D2","func":"01","type":"12","sender_id":"0xFFAAE008","actuator_type":"switch","channel":1,"description":"Kueche","manufacturer":"NodOn"}'     "D2-01-12 channel 2"

log "seeding states"
exec ./seed-states.sh
