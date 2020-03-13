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
from .mpputils import mppUtils, log
import time

grab_settings = False


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description='MPP Solar Inverter Info Utility')
    parser.add_argument('-s', '--grabsettings', action='store_true', help='Also get the inverter settings')
    parser.add_argument('-d', '--device', type=str, help='Serial device(s) to communicate with [comma separated]',
                        default='/dev/hidraw0')
    parser.add_argument('-b', '--baud', type=int, help='Baud rate for serial communications', default=2400)
    parser.add_argument('-q', '--broker', type=str, help='MQTT Broker hostname', default='mqtt_broker')
    parser.add_argument('-o', '--brokerport', type=int, help='MQTT Broker port', default=1883)
    parser.add_argument('-u', '--username', type=str, help='MQTT Broker username', default='cooluser')
    parser.add_argument('-P', '--password', type=str, help='MQTT Broker password', default='toocoolforschool')
    parser.add_argument('-p', '--prefix', type=str, help='MQTT Topic prefix', default='inverters')
    parser.add_argument('-U', '--publishunits', action='store_true', help='Publish Units?')
    parser.add_argument('-D', '--enableDebug', action='store_true', help='Enable Debug')
    parser.add_argument('-O', '--onceoff', action='store_true', help='Run Once-Off')
    parser.add_argument('-I', '--interval', type=int, help='Number of seconds between publishing telemetry', default=30)
    parser.add_argument('-L', '--listen', action='store_true', help='Listen for commands')
    parser.add_argument('-Q', '--queries', type=str, help='Queries to run per loop in CSV format', default='Q1,QPIGS')
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

    def __init__(self, someArgs):
        self.args = someArgs
        ports = self.args.device.split(',')

        for usb_port in ports:
            mp = mppUtils(serial_device=usb_port, baud_rate=self.args.baud)
            self.devs.append(mp)

            # Collect Inverter Settings and publish
            if self.args.grabsettings:
                msgs = []
                settings = mp.getSettings()

                for setting in settings:
                    for i in ['value', 'default', 'unit']:
                        topic = '/{}/{}/settings/{}/{}'.format(self.args.prefix, mp.serial_number, setting, i)
                        msg = {'topic': topic, 'payload': '{}'.format(settings[setting][i])}
                        msgs.append(msg)
                # publish.multiple(msgs, hostname=args.broker)
                log.debug(msgs)
                log.debug(self.args.broker)

    def conformNumber(self, number):
        try:
            if number.isdigit() and '.' in number:
                return float(number)
            elif number.isdigit():
                return int(number)
            else:
                return number
        except:
            return number

    def getTime(self):
        return int(round(time.time() * 1000))

    def run(self):
        if self.args.onceoff:
            self.publishTelemetry()
            return

        # threading.Timer(self.args.interval, self.publishTelemetry).start()
        self.initialiseClient()

        while True:
            if not self.mqttConnected:
                time.sleep(1)
                continue

            if (self.getTime() - self.lastPubRun) > self.args.interval * 1000:
                self.publishTelemetry()
                self.lastPubRun = self.getTime()

            self.mq.loop()
            time.sleep(0.01)

    def initialiseClient(self):
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
        log.debug(["got message", client, message.topic, str(message.payload)])
        if self.args.listen:
            print(client, message)

        payload = str(message.payload)
        args = str(message.topic).split('/')
        # "/inverters/92932001102598/settings/bla"
        print(args)  # ['', 'inverters', '92932001102598', 'settings', 'PCVV59.3']
        serialNumber = args[2]
        command = args[4]

        log.debug("got command")
        print(command)
        resp = self.mp.getResponse(command)
        log.debug(resp)
        # resp = json.dumps(resp)
        # log.debug(resp)
        # print(str(resp))
        self.mq.publish("/" + args[1] + "/" + args[2] + "/response", resp)

    def handleDisconnect(self, client, userdata, rc):
        log.debug(["got disconnected", client, userdata, rc])
        self.mqttConnected = False

        self.initialiseClient()

    def handleConnect(self, client, userdata, flags, rc, properties=None):
        self.mqttConnected = True
        self.mq.subscribe('/{}/+/settings/#'.format(self.args.prefix))

    def publishTelemetry(self):
        try:
            # Process / loop through all supplied devices
            for dev in self.devs:
                # Collect Inverter Status data and publish
                msgs = []
                status_data = dev.getFullStatus(queries=self.args.queries)
                for status_line in status_data:
                    for i in ['value', 'unit']:
                        if (self.args.publishunits and i is 'unit') or (
                                self.args.publishunits is False and i is not 'unit'):
                            # 92931509101901/status/total_output_active_power/value 1250
                            # 92931509101901/status/total_output_active_power/unit W
                            topic = '/{}/{}/status/{}/{}'.format(self.args.prefix, dev.serial_number, status_line, i)
                            msg = {'topic': topic, 'payload': '{}'.format(self.conformNumber(status_data[status_line][i]))}
                            msgs.append(msg)
                for msg in msgs:
                    self.mq.publish(msg["topic"], payload=msg["payload"])
                log.debug(msgs)
                log.debug(self.args.broker)
                log.debug(status_data)
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
