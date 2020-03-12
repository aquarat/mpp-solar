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
import logging
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
from .mpputils import mppUtils, log
import threading

grab_settings = False


def conformNumber(number):
    try:
        if number.isdigit() and '.' in number:
            return float(number)
        elif number.isdigit():
            return int(number)
        else:
            return number
    except:
        return number


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

    print(args)

    mpp = MPPSolarMain(args)
    mpp.run()


class MPPSolarMain:
    args = None
    mq = None

    def __init__(self, someArgs):
        self.args = someArgs

    def run(self):
        if self.args.onceoff:
            self.publishTelemetry()
            return

        threading.Timer(self.args.interval, self.publishTelemetry).start()

        self.initialiseClient()


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
        self.mq.loop_forever()
        # self.mq.loop_start()



    def handleMessage(self, client, userdata, message):
        log.debug(["got message", client, message])
        if self.args.listen:
            print(client, message)

    def handleDisconnect(self, client, userdata, rc):
        log.debug(["got disconnected", client, userdata, rc])
        mqttConnected = False

        self.initialiseClient()

    def handleConnect(self, client, userdata, flags, rc, properties=None):
        mqttConnected = True
        self.mq.subscribe('/{}/+/settings/#'.format(self.args.prefix))

    def publishTelemetry(self):
        # Process / loop through all supplied devices
        for usb_port in self.args.device.split(','):
            mp = mppUtils(usb_port, self.args.baud)
            serial_number = mp.getSerialNumber()

            # Collect Inverter Settings and publish
            if self.args.grabsettings:
                msgs = []
                settings = mp.getSettings()

                for setting in settings:
                    for i in ['value', 'default', 'unit']:
                        topic = '/{}/{}/settings/{}/{}'.format(self.args.prefix, serial_number, setting, i)
                        msg = {'topic': topic, 'payload': '{}'.format(settings[setting][i])}
                        msgs.append(msg)
                # publish.multiple(msgs, hostname=args.broker)
                log.debug(msgs)
                log.debug(self.args.broker)

            # Collect Inverter Status data and publish
            msgs = []
            status_data = mp.getFullStatus()
            for status_line in status_data:
                for i in ['value', 'unit']:
                    if (self.args.publishunits and i is 'unit') or (
                            self.args.publishunits is False and i is not 'unit'):
                        # 92931509101901/status/total_output_active_power/value 1250
                        # 92931509101901/status/total_output_active_power/unit W
                        topic = '/{}/{}/status/{}/{}'.format(self.args.prefix, serial_number, status_line, i)
                        msg = {'topic': topic, 'payload': '{}'.format(conformNumber(status_data[status_line][i]))}
                        msgs.append(msg)
            publish.multiple(msgs, hostname=self.args.broker, port=self.args.brokerport,
                             auth={'username': self.args.username, 'password': self.args.password})
            log.debug(msgs)
            log.debug(self.args.broker)
            log.debug(status_data)

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
