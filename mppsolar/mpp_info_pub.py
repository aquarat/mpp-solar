#!/usr/bin/python
#
#
# mpp_info_pub.py
#
# script to query MPP Solar PIP-4048MS inverter/charger
# - inverter connected to computer via serial
#      (USB to Serial converter used for testing)
# - posts results to MQTT broker
# - uses mpputils.py / mppcommands.py to abstract PIP communications
#
import json
import logging
import sys
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

from .mppinverter import getCommandsFromJson
from .mpputils import mppUtils, log
import time


def is_py3():
    if sys.version_info[0] < 3:
        return False

    return True

from .one_to_one_codec import init_custom_codec
if is_py3():
    init_custom_codec()

grab_settings = False


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description='MPP Solar Inverter Info Utility')
    parser.add_argument('-s', '--settings', action='store_true', help='Also get the inverter settings')
    parser.add_argument('-d', '--device', type=str, help='Serial device(s) to communicate with [comma separated]',
                        default='/dev/hidraw0')
    parser.add_argument('-b', '--baud', type=int, help='Baud rate for serial communications', default=2400)
    parser.add_argument('-q', '--broker', type=str, help='MQTT Broker hostname', default='mqtt_broker')
    parser.add_argument('-o', '--brokerport', type=int, help='MQTT Broker port', default=1883)
    parser.add_argument('-u', '--username', type=str, help='MQTT Broker username', default='cooluser')
    parser.add_argument('-P', '--password', type=str, help='MQTT Broker password', default='toocoolforschool')
    parser.add_argument('-p', '--prefix', type=str, help='MQTT Topic prefix', default='inverters')
    parser.add_argument('-D', '--enableDebug', action='store_true', help='Enable Debug')
    parser.add_argument('-O', '--onceoff', action='store_true', help='Run Once-Off')
    parser.add_argument('-I', '--interval', type=int, help='Number of seconds between publishing telemetry', default=30)
    parser.add_argument('-L', '--listen', action='store_true', help='Listen for commands')
    parser.add_argument('-Q', '--queries', type=str, help='Queries to run per loop in CSV format', default='Q1,QPIGS')
    parser.add_argument('-H', '--disable_ha_auto_config', action='store_true',
                        help='Disable publishing of Home Assistant auto config discovery.')
    parser.add_argument('-R', '--disable_ha_config_retain', action='store_true',
                        help='Disable retain on HA auto config')
    args = parser.parse_args()

    #
    # Turn on debug if needed
    if args.enableDebug:
        log.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        # add the handlers to logger
        log.addHandler(ch)

    mpp = MPPSolarMain(args)
    mpp.run()


class MPPSolarMain:
    args = None
    mq = None
    lastPubRun = 0
    mqttConnected = False
    devs = []
    commands = None

    def __init__(self, someArgs):
        self.args = someArgs
        ports = self.args.device.split(',')

        for usb_port in ports:
            mp = mppUtils(serial_device=usb_port, baud_rate=self.args.baud)
            self.devs.append(mp)

        self.commands = getCommandsFromJson()

    def doSettingsPublish(self, mp=None):
        # Collect Inverter Settings and publish
        if self.args.settings and mp is not None:
            settings = mp.getSettings()

            for setting in settings:
                topic = '/{}/{}/settings/{}/{}'.format(self.args.prefix, mp.serial_number, setting, 'value')
                self.mq.publish(topic, payload='{}'.format(settings[setting]['value']))

    @staticmethod
    def conformNumber(number):
        try:
            if number.isdigit() and '.' in number:
                return float(number)
            elif number.isdigit():
                return int(number)
            elif str(number).find("\t- ") > 0:
                number = str(number)
                number = number[number.find("- ") + 2:]
                return number
            else:
                return number
        except:
            return number

    @staticmethod
    def getTime():
        return int(round(time.time() * 1000))

    def run(self):
        self.initialise_client()

        while True:
            if not self.mqttConnected:
                time.sleep(1)
                continue

            if (self.getTime() - self.lastPubRun) > self.args.interval * 1000:
                self.publishTelemetry()
                self.lastPubRun = self.getTime()

            self.mq.loop()
            if self.args.onceoff:
                return
            time.sleep(0.01)

    def initialise_client(self):
        self.mq = mqtt.Client(clean_session=True, userdata=None, transport="tcp")
        self.mq.username_pw_set(username=self.args.username, password=self.args.password)
        self.mq.will_set('/{}/lwt'.format(self.args.prefix), payload="offline")
        self.mq.on_disconnect = self.handleDisconnect
        self.mq.on_message = self.handleMessage
        self.mq.on_connect = self.handleConnect
        self.mq.connect(self.args.broker,
                        port=self.args.brokerport,
                        keepalive=30)
        # self.mq.loop_forever()
        self.mq.loop_start()

    def handleMessage(self, client, userdata, message):
        args = str(message.topic).split('/')
        # "/inverters/92932001102598/settings/bla"
        serialNumber = args[2]
        command = args[4]

        log.debug("got command '{}' for {}".format(command, serialNumber))
        try:
            for dev in self.devs:
                if dev.serial_number == serialNumber:
                    resp = dev.getResponse(command)
                    log.debug("Command response: {}".format(json.dumps(resp)))
                    self.mq.publish("/{}/{}/response".format(self.args.prefix, serialNumber), resp)

                    return
        except:
            log.error(sys.exc_info()[0])

        log.debug("Target device for specified serial number and command not found.")

    def handleDisconnect(self, client, userdata, rc):
        log.debug(["got disconnected", client, userdata, rc])
        self.mqttConnected = False

        self.initialiseClient()

    def handleConnect(self, client, userdata, flags, rc, properties=None):
        self.mqttConnected = True
        for dev in self.devs:
            self.mq.subscribe('/{}/{}/settings/#'.format(self.args.prefix, dev.serial_number))

        if not self.args.disable_ha_auto_config:
            for dev in self.devs:
                for c in self.commands:
                    pass #TODO

    def publishTelemetry(self):
        try:
            # Process / loop through all supplied devices
            for dev in self.devs:
                # Collect Inverter Status data and publish
                status_data = dev.getFullStatus(queries=self.args.queries, extraFlagData=True)
                for status_line in status_data:
                    # 92931509101901/status/total_output_active_power/value 1250
                    # 92931509101901/status/total_output_active_power/unit W
                    topic = '/{}/{}/status/{}/{}'.format(self.args.prefix,
                                                         dev.serial_number,
                                                         status_line,
                                                         'value')
                    payload = '{}'.format(self.conformNumber(status_data[status_line]['value']))
                    self.mq.publish(topic,
                                    payload=payload)
                log.debug(status_data)

                self.doSettingsPublish(mp=dev)

        except:
            log.error(sys.exc_info()[0])

# Adafruit IO has:
#    Battery Capacity (as %)         inverter-one-battery-capacity-percent
#    Output Power (W)                inverter-one-total-output-active-power-w
#    Fault Code (text text)          fault-code
#    Battery Voltage                 inverter-one-battery-voltage-v
#    Inverter Charge Status (text)   inverter-charge-status
#    Total Charging Current (A)      inverter-one-total-charging-current-a
#    Inverter 1 charging current (A) inverter-one-battery-charging-current-a
#    Inverter 2 charging current (A) inverter-two-battery-charging-current-a
#    Load (as %)                     inverter-one-load-percentage-percent
