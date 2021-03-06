"""
MPP Solar Inverter Command Library
reference library of serial commands (and responses) for PIP-4048MS inverters
mppinverter.py
"""
import sys
import traceback

import serial
import time
import re
import logging
import json
import glob
import os
from os import path

from .mppcommand import mppCommand, ENCODING

log = logging.getLogger('MPP-Solar')


def is_py3():
    if sys.version_info[0] < 3:
        return False

    return True


class MppSolarError(Exception):
    pass


class NoDeviceError(MppSolarError):
    pass


class NoTestResponseDefined(MppSolarError):
    pass


def getDataValue(data, key):
    """
    Get value from data dict (loaded from JSON) or return empty String
    """
    if key == 'regex':
        if 'regex' in data and data['regex']:
            return re.compile(data['regex'])
        else:
            return None
    if key in data:
        return data[key]
    else:
        return ""


# file:///home/aquarat/Downloads/PIP-GK_MK%20Protocol.pdf
def getCommandsFromJson():
    """
    Read in all the json files in the commands subdirectory
    this builds a list of all valid commands
    """
    COMMANDS = []
    here = path.abspath(path.dirname(__file__))
    files = glob.glob(here + '/commands/*.json')

    for file in sorted(files):
        log.debug("Loading command information from {}".format(file))
        with open(file) as f:
            try:
                data = json.load(f)
            except Exception:
                log.debug("Error processing JSON in {}".format(file), exc_info=True)
                continue
            COMMANDS.append(mppCommand(getDataValue(data, 'name'), getDataValue(data, 'description'),
                                       getDataValue(data, 'type'), getDataValue(data, 'response'),
                                       getDataValue(data, 'test_responses'), getDataValue(data, 'regex'),
                                       help=getDataValue(data, 'help')))
    return COMMANDS


def isTestDevice(serial_device):
    """
    Determine if this instance is just a Test connection
    """
    if serial_device == 'TEST':
        return True
    return False


def isDirectUsbDevice(serial_device):
    """
    Determine if this instance is using direct USB connection
    (instead of a serial connection)
    """
    if not serial_device:
        return False
    match = re.search("^.*hidraw\\d$", str(serial_device))
    if match:
        log.debug("Device matches hidraw regex")
        return True
    return False


class mppInverter:
    """
    MPP Solar Inverter Command Library
    - represents an inverter (and the commands the inverter supports)
    """

    def __init__(self, serial_device=None, baud_rate=2400):
        if not serial_device:
            raise NoDeviceError("A device to communicate by must be supplied, e.g. /dev/ttyUSB0")
        self._baud_rate = baud_rate
        self._serial_device = serial_device
        self._serial_number = None
        self._test_device = isTestDevice(serial_device)
        self._direct_usb = isDirectUsbDevice(serial_device)
        self._commands = getCommandsFromJson()
        # TODO: text descrption of inverter? version numbers?

    def __str__(self):
        """
        """
        inverter = "\n"
        if self._direct_usb:
            inverter = "Inverter connected via USB on {}".format(self._serial_device)
        elif self._test_device:
            inverter = "Inverter connected as a TEST"
        else:
            inverter = "Inverter connected via serial port on {}".format(self._serial_device)
        inverter += "\n-------- List of supported commands --------\n"
        if self._commands:
            for cmd in self._commands:
                inverter += str(cmd)
        return inverter

    def getSerialNumber(self):
        if self._serial_number is None:
            response = self.execute("QID").getResponseDict()
            if response:
                self._serial_number = response["serial_number"][0]
        return self._serial_number

    def getAllCommands(self):
        """
        Return list of defined commands
        """
        return self._commands

    def _getCommand(self, cmd):
        """
        Returns the mppcommand object of the supplied cmd string
        """
        log.debug("Searching for cmd '{}'".format(cmd))
        if not self._commands:
            log.debug("No commands found")
            return None
        for command in self._commands:
            if not command.regex:
                if cmd == command.name:
                    return command
            else:
                match = command.regex.match(cmd)
                if match:
                    log.debug(command.name, command.regex)
                    log.debug("Matched: {} Value: {}".format(command.name, match.group(1)))
                    command.setValue(match.group(1))
                    return command
        return None

    def _doTestCommand(self, command):
        """
        Performs a test command execution
        """
        command.clearResponse()
        log.debug('Performing test command with %s', command)
        command.setResponse(command.getTestResponse())
        return command

    def _doSerialCommand(self, command):
        """
        Opens serial connection, sends command (multiple times if needed)
        and returns the response
        """
        command.clearResponse()
        response_line = None
        log.debug('port %s, baudrate %s', self._serial_device, self._baud_rate)
        try:
            with serial.serial_for_url(self._serial_device, self._baud_rate) as s:
                # Execute command multiple times, increase timeouts each time
                for x in range(1, 5):
                    log.debug('Command execution attempt %d...', x)
                    s.timeout = 1 + x
                    s.write_timeout = 1 + x
                    s.flushInput()
                    s.flushOutput()
                    s.write(command.full_command)
                    time.sleep(0.5 * x)  # give serial port time to receive the data
                    response_line = s.readline()
                    log.debug('serial response was: %s', response_line)
                    command.setResponse(response_line)
                    return command
        except Exception as e:
            log.debug('Serial read error', e.strerror)
        log.info('Command execution failed')
        return command

    def _doDirectUsbCommand(self, command):
        """
        Opens direct USB connection, sends command (multiple times if needed)
        and returns the response
        """
        command.clearResponse()
        response_line = ""
        usb0 = None
        try:
            try:
                usb0 = os.open(self._serial_device, os.O_RDWR | os.O_NONBLOCK)
            except Exception as e:
                log.debug('USB open error', e.strerror)
                return command
            # Send the command to the open usb connection
            to_send = command.full_command
            while (len(to_send) > 0):
                # Split the full command into smaller chucks
                send, to_send = to_send[:8], to_send[8:]
                time.sleep(0.35)
                if is_py3():
                    send = send.encode(ENCODING)
                os.write(usb0, send)
            time.sleep(0.25)
            # Read from the usb connection
            # try to a max of 100 times
            for x in range(100):
                # attempt to deal with resource busy and other failures to read
                try:
                    time.sleep(0.15)
                    r = os.read(usb0, 256)
                    if is_py3():
                        r = r.decode(ENCODING)
                    response_line += r
                except Exception as e:
                    log.debug('USB read error')
                # Finished is \r is in response
                if ('\r' in response_line):
                    # remove anything after the \r
                    response_line = response_line[:response_line.find('\r') + 1]
                    break
            log.debug('usb response was: %s', response_line)
            command.setResponse(response_line)
        except Exception as err:
            log.error(err)
            traceback.print_exc()

        try:
            if usb0 is not None:
                os.close(usb0)
        except:
            pass

        return command

    locked = False

    def execute(self, cmd):
        """
        Sends a command (as supplied) to inverter and returns the raw response
        """
        while self.locked:
            time.sleep(0.1)
        self.locked = True

        doCommand = None

        for i in range(0, 10):
            try:
                command = self._getCommand(cmd)

                if command is None:
                    log.critical("Command not found")
                elif (self._test_device):
                    log.debug('TEST connection: executing %s', command)
                    doCommand = self._doTestCommand(command)
                elif (self._direct_usb):
                    log.debug('DIRECT USB connection: executing %s', command)
                    doCommand = self._doDirectUsbCommand(command)
                else:
                    log.debug('SERIAL connection: executing %s', command)
                    doCommand = self._doSerialCommand(command)
            except Exception as err:
                log.error(sys.exc_info()[0])
                log.error(err)

            if doCommand.getResponse() is not None and doCommand.isResponseValid(doCommand.getResponse()):
                break

            log.debug("Received empty response. Retrying attempt {} of {}...".format(i, 10))
            time.sleep(1)

        self.locked = False

        return doCommand
