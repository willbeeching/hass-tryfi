import logging
import datetime
from .ledColors import ledColors
from .const import PET_MODE_NORMAL, PET_MODE_LOST
from ._reporting import capture_exception

LOGGER = logging.getLogger(__name__)

class FiDevice(object):
    def __init__(self, deviceId):
        self._deviceId = deviceId
        # hass-tryfi: every attribute exists from the start. Upstream set them
        # one by one inside a single try, so the first field a collar did not
        # report left every later one undefined, and Home Assistant then raised
        # AttributeError on each refresh (sbabcock23/hass-tryfi#69 `_ledOn`,
        # #100 `_mode`). None means "not reported".
        self._moduleId = None
        self._buildId = None
        self._batteryPercent = None
        self._isCharging = False
        self._ledOffAt = None
        self._ledOn = None
        self._mode = None
        self._ledColor = None
        self._ledColorHex = None
        self._connectionStateDate = None
        self._connectionStateType = None
        self._connectionSignalStrength = None
        self._connectedBaseId = None
        self._connectedUserFirstName = None
        self._availableLedColors = []
        self._lastUpdated = None

    # hass-tryfi: each group of fields is read on its own, so one a collar
    # leaves out (the Fi Mini and Series 3+ report less) costs only itself.
    # A group that fails keeps whatever it held before.
    def setDeviceDetailsJSON(self, deviceJSON):
        for group in (self._readModule, self._readInfo, self._readOperation,
                      self._readLedColor, self._readConnection, self._readLedColors):
            try:
                group(deviceJSON)
            except Exception as e:
                LOGGER.debug(f"tryfi Error: {e}")
                capture_exception(e)
        self._lastUpdated = datetime.datetime.now()

    def _readModule(self, deviceJSON):
        self._moduleId = deviceJSON['moduleId']

    def _readInfo(self, deviceJSON):
        info = deviceJSON['info']
        self._buildId = info.get('buildId')
        self._batteryPercent = int(info['batteryPercent']) if info.get('batteryPercent') is not None else None
        #V1 of the collar has this parameter but V2 it is missing
        self._isCharging = bool(info.get('isCharging', False))

    def _readOperation(self, deviceJSON):
        params = deviceJSON['operationParams']
        self._mode = params.get('mode')
        self._ledOffAt = self.setLedOffAtDate(params.get('ledOffAt'))
        self._ledOn = self.getAccurateLEDStatus(bool(params.get('ledEnabled')))

    def _readLedColor(self, deviceJSON):
        self._ledColor = deviceJSON['ledColor']['name']
        self._ledColorHex = deviceJSON['ledColor']['hexCode']

    def _readConnection(self, deviceJSON):
        state = deviceJSON['lastConnectionState']
        self._connectionStateType = state['__typename']
        # hass-tryfi: the detail behind the connection type, structured rather
        # than flattened into one string (sbabcock23/hass-tryfi#60).
        self._connectionSignalStrength = state.get('signalStrengthPercent')
        self._connectedBaseId = (state.get('chargingBase') or {}).get('id')
        self._connectedUserFirstName = (state.get('user') or {}).get('firstName')
        self._connectionStateDate = datetime.datetime.fromisoformat(str(state['date']).replace('Z', '+00:00'))

    def _readLedColors(self, deviceJSON):
        colors = []
        for cString in deviceJSON['availableLedColors'] or []:
            colors.append(ledColors(int(cString['ledColorCode']), cString['hexCode'], cString['name']))
        self._availableLedColors = colors

    def __str__(self):
        return f"Last Updated - {self.lastUpdated} - Device ID: {self.deviceId} Device Mode: {self.mode} Battery Left: {self.batteryPercent}% LED State: {self.ledOn} Last Connected: {self.connectionStateDate} by: {self.connectionStateType}"

    @property
    def deviceId(self):
        return self._deviceId
    @property
    def moduleId(self):
        return self._moduleId
    @property
    def mode(self):
        return self._mode
    @property
    def buildId(self):
        return self._buildId
    @property
    def batteryPercent(self):
        return self._batteryPercent
    #This was deprecated in the newer collars
    #@property
    #def batteryHealth(self):
    #    return self._batteryHealth
    @property
    def isCharging(self):
        return self._isCharging
    @property
    def ledOn(self):
        return self._ledOn
    @property
    def ledOffAt(self):
        return self._ledOffAt
    @property
    def ledColor(self):
        return self._ledColor
    @property
    def ledColorHex(self):
        return self._ledColorHex
    @property
    def connectionStateDate(self):
        return self._connectionStateDate
    @property
    def connectionStateType(self):
        return self._connectionStateType
    @property
    def connectionSignalStrength(self):
        return self._connectionSignalStrength
    @property
    def connectedBaseId(self):
        return self._connectedBaseId
    @property
    def connectedUserFirstName(self):
        return self._connectedUserFirstName
    @property
    def availableLedColors(self):
        return self._availableLedColors
    @property
    def lastUpdated(self):
        return self._lastUpdated
    @property
    def isLost(self):
        if self._mode == PET_MODE_LOST:
            return True
        else:
            return False

#This is created because if TryFi automatically turns off the LED, the status is still set to true in the api.
#This will compare the dates to see if the current date/time is greater than the turnoffat time in the api.
    def getAccurateLEDStatus(self, ledStatus):
        if ledStatus is False:
            LOGGER.debug("getAccurateLedStatus: LED Status is False")
            return False
        else:
            LOGGER.debug("getAccurateLedStatus: LED Status is True... comparing date/times")
            currentDateTime = datetime.datetime.now(datetime.timezone.utc)
            if currentDateTime > self.ledOffAt:
                LOGGER.debug(f"Current datetime: {currentDateTime} is greater than ledOffAt: {self.ledOffAt}, Returning False")
                return False
            else:
                LOGGER.debug(f"Current datetime: {currentDateTime} is less than ledOffAt: {self.ledOffAt}, Returning False")
                return True
#Created function to return a date/time regardless.
    def setLedOffAtDate(self, ledOffAt):
        if ledOffAt == None:
            ## if object is null, return current date/time in UTC
            LOGGER.debug("LedOffAt is None, returning current datetime in UTC")
            return datetime.datetime.now(datetime.timezone.utc)
        else:
            LOGGER.debug(f"LedOffAt has date/time of {ledOffAt}. Returning this in ISO Format.")
            return datetime.datetime.fromisoformat(str(ledOffAt).replace('Z', '+00:00'))