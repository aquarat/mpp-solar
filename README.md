# Voltronic Axpert King Inverter MQTT Bridge

Python query/monitoring application for the Voltronic Axpert King Series of Hybrid Inverters.

This application specifically targets the PIP-5048MK type inverter.

Also known as:
- SOL-I-AX-5KP

More info:
- Protocol definition: https://forums.aeva.asn.au/download/file.php?id=1376
- General community discussion: https://forums.aeva.asn.au/viewtopic.php?f=64&t=5955
- South African Power Forum: https://powerforum.co.za/topic/5343-beta-patched-firmware-version-7440e/?tab=comments#comment-71807

## Pictures
<p align="center">
  <img src="https://github.com/aquarat/mpp-solar/blob/master/images/ha-lovelace-card.png?raw=true" alt="A Lovelace card in the Home Assistant web interface."/>
  <img src="https://github.com/aquarat/mpp-solar/blob/master/images/example-ha-graph.png?raw=true" alt="A Lovelace card in the Home Assistant web interface."/>
  <img src="https://github.com/aquarat/mpp-solar/blob/master/images/rpi-zero-w-backpowered.jpg?raw=true" alt="An RPi Zero W being back-powered from the inverter's USB OTG port."/>
</p>

## Notes
- This app is now functional - it just needs polishing.
- My goal is to integrate my Axpert King inverter into Home Assistant via an MQTT broker.
- Home Assistant sensor definitions are present for most fields of interest at the bottom of this file.
- This application should be able to handle multiple inverters, but I don't have multiple inverters to test it with.

## TODO
- [x] Bi-directional communication (get and set via MQTT). This currently works for a limited subset of commands. Some documented commands respond with an ACK but don't actually apply the setting.
- [ ] Double-check current payload/command definitions against protocol PDF. (Largely done)
- [x] Determine why queries fail when utility power goes away.
- [x] Make compliant with Python 3.
- [ ] Publish HA auto-config payload.
- [ ] Fix bug where terminal gets corrupted (funny characters).
- [ ] Fix bug where synchronisation-like bug occurs causing "not all elements formatted" errors (they only last for one loop anyway).
- [ ] Add hardware flow control (will have to use PySerial probably).

## Thank you
to the guy that wrote the original code (https://github.com/jblance/mpp-solar). I was so happy when 
(1) I saw it mostly worked and 
(2) noted how it had been written to be flexible.

## Tested On
- a Raspberry Pi Zero W
- being back-powered through the USB port on the Pi from the inverter's OTG port.

## Install
`python ./setup.py install`

## Usage
Run without installing:
- Run once-off help:
`python2 -c "import mppsolar; mppsolar.main()" -h`
- Run MQTT publish:
`python2 -c \"import mppsolar; import mppsolar.mpp_info_pub; mppsolar.mpp_info_pub.main()\" -d /dev/hidraw0 -q mqttiporhostname -u username -P password"`
- Run MQTT publish as cron job:
`* * * * * root /bin/bash -c "cd /home/aquarat/mppsolar; python2 -c \"import mppsolar; import mppsolar.mpp_info_pub; mppsolar.mpp_info_pub.main()\" -d /dev/hidraw0 -q mqttiporhostname -u username -P password";`
or with custom query flags and various other TIDBITS:
`/bin/bash -c "cd /home/aquarat/mppsolar; python2 -c \"import mppsolar; import mppsolar.mpp_info_pub; mppsolar.mpp_info_pub.main()\" -d /dev/hidraw0 -q 10.0.0.81 -u username -P password -D -I 30 -L -Q \"Q1,QPIGS,QMOD,QPIWS\"";`
- See bottom for Home Assistant sensor definitions.
- Payloads dispatched to broker look like this: `/inverters/92932001102598/status/is_load_on/value 1`

### Once-off query/set:
`$ mpp-solar -h`
```
usage: -c [-h] [-c COMMAND] [-D] [-d DEVICE] [-b BAUD] [-l] [-s] [-t] [-R]

MPP Solar Command Utility

optional arguments:
  -h, --help            show this help message and exit
  -c COMMAND, --command COMMAND
                        Command to run
  -D, --enableDebug     Enable Debug
  -d DEVICE, --device DEVICE
                        Serial device to communicate with
  -b BAUD, --baud BAUD  Baud rate for serial communications
  -l, --listknown       List known commands
  -s, --getStatus       Get Inverter Status
  -t, --getSettings     Get Inverter Settings
  -R, --showraw         Display the raw results
```

## Available Commands
`$ mpp-solar -l`
```
-------- List of known commands --------
MCHGC: Set Max Charging Current (for parallel units)
MUCHGC: Set Utility Max Charging Current
PBT: Set Battery Type
PCP: Set Device Charger Priority
PCVV: Set Battery C.V. (constant voltage) charging voltage
POP: Set Device Output Source Priority
PSDV: Set Battery Cut-off Voltage
Q1: Q1 query
QBOOT: DSP Has Bootstrap inquiry
QDI: Device Default Settings inquiry
QFLAG: Device Flag Status inquiry
QID: Device Serial Number inquiry
QMCHGCR: Max Charging Current Options inquiry
QMOD: Device Mode inquiry
QMUCHGCR: Max Utility Charging Current Options inquiry
QOPM: Output Mode inquiry
QPGSn: Parallel Information inquiry
QPI: Device Protocol ID inquiry
QPIGS: Device General Status Parameters inquiry
QPIRI: Device Current Settings inquiry
QPIWS: Device warning status inquiry
QVFW: Main CPU firmware version inquiry
QVFW2: Secondary CPU firmware version inquiry
```

## Example
`$ mpp-solar -s`
```
================ Status ==================
Parameter                       Value           Unit
ac_input_frequency              00.0            Hz
ac_input_voltage                000.0           V
ac_output_active_power          0152            W
ac_output_apparent_power        0207            VA
ac_output_frequency             50.0            Hz
ac_output_load                  004             %
ac_output_voltage               230.2           V
allowscconflag                  01
battery_capacity                100             %
battery_charging_current        018             A
battery_discharge_current       00000           A
battery_temperature             046             Deg_C
battery_voltage                 57.40           V
battery_voltage_from_scc        57.45           V
bus_voltage                     459             V
chargeaveragecurrent            00
fan_lock_status                 Not locked
fan_pwm_speed                   0030            Percent
inverter_charge_status          bulk stage
inverter_heat_sink_temperature  0057            Deg_C
inverter_temperature            034             Deg_C
pv_input_current_for_battery    0021            A
pv_input_voltage                069.9           V
scc_charge_power                1258            W
scc_flag                        SCC is powered and communicating
scc_pwm_temperature             051             Deg_C
sync_frequency                  50.00
transformer_temperature         057             Deg_C
```

## Home Assistant Sensor Definitions
```
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_input_frequency/value"
    name: "ac_input_frequency"
    expire_after: 360
    unit_of_measurement: 'Hz'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_output_frequency/value"
    name: "ac_output_frequency"
    expire_after: 360
    unit_of_measurement: 'Hz'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/pv_input_voltage/value"
    name: "pv_input_voltage"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_output_voltage/value"
    name: "ac_output_voltage"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_input_voltage/value"
    name: "ac_input_voltage"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_voltage/value"
    name: "battery_voltage"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_voltage_from_scc/value"
    name: "battery_voltage_from_scc"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/bus_voltage/value"
    name: "bus_voltage"
    expire_after: 360
    unit_of_measurement: 'V'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/inverter_charge_status/value"
    name: "inverter_charge_status"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/inverter_temperature/value"
    name: "inverter_temperature"
    expire_after: 360
    unit_of_measurement: '°C'
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/transformer_temperature/value"
    name: "transformer_temperature"
    expire_after: 360
    unit_of_measurement: '°C'
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_temperature/value"
    name: "battery_temperature"
    expire_after: 360
    unit_of_measurement: '°C'
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/inverter_heat_sink_temperature/value"
    name: "inverter_heat_sink_temperature"
    expire_after: 360
    unit_of_measurement: '°C'
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_charging_current/value"
    name: "battery_charging_current"
    expire_after: 360
    unit_of_measurement: 'A'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/chargeaveragecurrent/value"
    name: "charge_average_current"
    expire_after: 360
    unit_of_measurement: 'A'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_discharge_current/value"
    name: "battery_discharge_current"
    expire_after: 360
    unit_of_measurement: 'A'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/pv_input_current_for_battery/value"
    name: "pv_input_current_for_battery"
    expire_after: 360
    unit_of_measurement: 'A'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/battery_capacity/value"
    name: "battery_capacity"
    expire_after: 360
    unit_of_measurement: '%'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_output_load/value"
    name: "ac_output_load"
    expire_after: 360
    unit_of_measurement: '%'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/is_charging_on/value"
    name: "is_charging_on"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/is_battery_voltage_to_steady_while_charging/value"
    name: "is_battery_voltage_to_steady_while_charging"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/is_ac_charging_on/value"
    name: "is_ac_charging_on"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/time_until_the_end_of_float_charging/value"
    name: "time_until_the_end_of_float_charging"
    unit_of_measurement: 'm'
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/fan_pwm_speed/value"
    name: "fan_pwm_speed"
    expire_after: 360
    unit_of_measurement: '%'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_output_apparent_power/value"
    name: "ac_output_apparent_power"
    expire_after: 360
    unit_of_measurement: 'W'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/ac_output_active_power/value"
    name: "ac_output_active_power"
    expire_after: 360
    unit_of_measurement: 'W'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/scc_flag/value"
    name: "scc_flag"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/is_scc_charging_on/value"
    name: "is_scc_charging_on"
    expire_after: 360
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/scc_charge_power/value"
    name: "scc_charge_power"
    expire_after: 360
    unit_of_measurement: 'W'
    device_class: power
  - platform: mqtt
    state_topic: "/inverters/92932001102598/status/time_until_the_end_of_absorb_charging/value"
    name: "is_scc_charging_on"
    expire_after: 360
    unit_of_measurement: 'm'
    device_class: power


```
