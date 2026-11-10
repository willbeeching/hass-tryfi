import datetime

class FiBase(object):
    def __init__(self, baseId):
        self._baseId = baseId
        # hass-tryfi: defaults, and each field read with .get, so a base TryFi
        # describes without some of them still loads. Upstream left the
        # attributes undefined and the base platform failed to set up
        # (sbabcock23/hass-tryfi#93).
        self._name = baseId
        self._latitude = None
        self._longitude = None
        self._online = None
        self._onlineQuality = None
        self._networkName = None
        self._lastUpdated = None

    def setBaseDetailsJSON(self, baseJSON):
        position = baseJSON.get('position') or {}
        self._name = baseJSON.get('name') or self._baseId
        self._latitude = position.get('latitude')
        self._longitude = position.get('longitude')
        self._online = baseJSON.get('online')
        self._onlineQuality = baseJSON.get('onlineQuality')
        self._networkName = baseJSON.get('networkName')
        self._lastUpdated = datetime.datetime.now()

    def __str__(self):
        return f"Last Updated - {self.lastUpdated} - Base ID: {self.baseId} Name: {self.name} Online Status: {self.online} Wifi Network: {self.networkname} Located: {self.latitude},{self.longitude}"
        
    @property
    def baseId(self):
        return self._baseId
    @property
    def name(self):
        return self._name
    @property
    def latitude(self):
        return self._latitude
    @property
    def longitude(self):
        return self._longitude
    @property
    def online(self):
        return self._online
    @property
    def onlineQuality(self):
        return self._onlineQuality
    @property
    def lastupdate(self):
        return self._lastUpdated
    @property
    def networkname(self):
        return self._networkName
    @property
    def lastUpdated(self):
        return self._lastUpdated