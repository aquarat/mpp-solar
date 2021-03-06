"""
MPP Solar Inverter Command Library
library of utility and helpers for MPP Solar PIP-4048MS inverters
mpputils.py
"""

import logging
from .mppinverter import mppInverter
from .mppinverter import NoDeviceError

log = logging.getLogger('MPP-Solar')


def getVal(_dict, key, ind=None):
    if key not in _dict:
        return ""
    if ind is None:
        return _dict[key]
    else:
        return _dict[key][ind]


class mppUtils:
    """
    MPP Solar Inverter Utility Library
    """

    serial_number = None

    def __init__(self, serial_device=None, baud_rate=2400):
        if (serial_device is None):
            raise NoDeviceError("A serial device must be supplied, e.g. /dev/ttyUSB0")
        self.inverter = mppInverter(serial_device, baud_rate)
        self.getSerialNumber()

    def getKnownCommands(self):
        return self.inverter.getAllCommands()

    def getResponseDict(self, cmd):
        return self.inverter.execute(cmd).getResponseDict()

    def getResponse(self, cmd):
        return self.inverter.execute(cmd).getResponse()

    def getSerialNumber(self):
        if self.serial_number is None:
            self.serial_number = self.inverter.getSerialNumber()

        return self.serial_number

    def getFullStatus(self, queries="Q1,QPIGS", extraFlagData=False):
        """
        Helper function that returns all the status data
        """
        status = {}
        # serial_number = self.getSerialNumber()
        data = {}
        for i in queries.split(","):
            data.update(self.getResponseDict(i))

        # Need to get 'Parallel' info, but dont know what the parallel number for the correct inverter is...
        # parallel_data = self.mp.getResponseDict("QPGS0")
        # This 'hack' only works for 2 inverters in parallel.
        # if parallel_data['serial_number'][0] != self.getSerialNumber():
        #    parallel_data = self.mp.getResponseDict("QPGS1")
        # status_data.update(parallel_data)

        for item in data.keys():
            key = '{}'.format(item).replace(" ", "_")
            status[key] = {"value": data[key][0], "unit": data[key][1]}
        # Still have 'Device Status' from QPIGS
        # Still have QPGSn
        return status

    def getSettings(self):
        """
        Query inverter for all current settings
        """
        # serial_number = self.getSerialNumber()
        default_settings = self.getResponseDict("QDI")
        current_settings = self.getResponseDict("QPIRI")
        flag_settings = self.getResponseDict("QFLAG")
        # current_settings.update(flag_settings)  # Combine current and flag settings dicts

        settings = {}
        # {"Battery Bulk Charge Voltage": {"unit": "V", "default": 56.4, "value": 57.4}}

        for item in current_settings.keys():
            key = '{}'.format(item).replace(" ", "_")
            settings[key] = {"value": getVal(current_settings, key, 0),
                             "unit": getVal(current_settings, key, 1),
                             "default": getVal(default_settings, key, 0)}
        for key in flag_settings:
            _key = '{}'.format(key).replace(" ", "_")
            if _key in settings:
                settings[_key]['value'] = getVal(flag_settings, key, 0)
            else:
                settings[_key] = {'value': getVal(flag_settings, key, 0), "unit": "", "default": ""}
        return settings
