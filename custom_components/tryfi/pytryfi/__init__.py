import logging
import requests

from .const import (API_HOST_URL_BASE, API_LOGIN, PYTRYFI_VERSION, HEADER)
from .fiUser import FiUser
from .fiPet import FiPet
from .fiBase import FiBase
from .common import query
from ._reporting import capture_message, capture_exception



LOGGER = logging.getLogger(__name__)

class PyTryFi(object):
    """base object for TryFi"""

    def __init__(self, username=None, password=None):
        try:
            self._api_host = API_HOST_URL_BASE
            self._session = requests.Session()
            self._user_agent = "pyTryFi"
            self._username = username
            self._password = password    
            self.login()
            #set Headers only after login for use going forward.
            self.setHeaders()

            self._currentUser = FiUser(self._userId)
            self._currentUser.setUserDetails(self._session)

            # hass-tryfi: each pet and base is loaded on its own, so one that
            # TryFi describes oddly no longer stops every other one loading.
            # One households query serves both; upstream made the same request
            # twice in a row, once for pets and once for bases.
            households = query.getPetList(self._session)
            self._pets = self._loadPets(households, {})
            self._bases = self._loadBases(households)
        except Exception as e:
            capture_exception(e)

    def __str__(self):
        instString = f"Username: {self.username}"
        userString = f"{self.currentUser}"
        baseString = ""
        petString = ""
        for b in self.bases:
            baseString = baseString + f"{b}"
        for p in self.pets:
            petString = petString + f"{p}"
        return f"TryFi Instance - {instString}\n Pets in Home:\n {petString}\n Bases In Home:\n {baseString}"
    
    #set the headers for the session
    def setHeaders(self):
        self.session.headers = HEADER

    #refresh pet details for all pets
    # hass-tryfi: a failure to fetch the account now raises rather than being
    # swallowed, so the caller can tell its data is stale, and a failure for one
    # pet keeps that pet's last readings instead of dropping every pet.
    def updatePets(self):
        previous = {p.petId: p for p in self._pets}
        self._pets = self._loadPets(query.getPetList(self._session), previous)

    # Pets without a collar are skipped. Upstream compared the device with the
    # string "None", but TryFi sends null, so a pet with only a microchip (a
    # Nano, a cat, a shared pet, a retired collar) raised a TypeError that
    # abandoned every pet on the account: "only the bases show up"
    # (sbabcock23/hass-tryfi#61, #62, #67, #87, #96, #99, #102).
    def _loadPets(self, households, previous):
        pets = []
        for house in households:
            for petJSON in (house.get('household') or {}).get('pets') or []:
                if not isinstance(petJSON.get('device'), dict):
                    LOGGER.debug(f"Pet {petJSON.get('name')} has no collar. Ignoring it.")
                    continue
                try:
                    pets.append(self._loadPet(petJSON, previous.get(petJSON['id'])))
                except Exception as e:
                    capture_exception(e)
                    old = previous.get(petJSON.get('id'))
                    if old is not None:
                        LOGGER.warning(f"Could not refresh pet {petJSON.get('name')}, keeping its last readings: {e}")
                        pets.append(old)
                    else:
                        LOGGER.warning(f"Could not load pet {petJSON.get('name')}, skipping it: {e}")
        return pets

    def _loadPet(self, petJSON, old):
        p = FiPet(petJSON['id'])
        p.setPetDetailsJSON(petJSON)
        steps = (
            (lambda: p.setCurrentLocation(query.getCurrentPetLocation(self._session, p._petId)), FiPet.LOCATION_ATTRS),
            (lambda: p.setStats(*self._periods(query.getCurrentPetStats(self._session, p._petId))), FiPet.STATS_ATTRS),
            (lambda: p.setRestStats(*self._periods(query.getCurrentPetRestStats(self._session, p._petId))), FiPet.REST_ATTRS),
        )
        for step, attrs in steps:
            try:
                step()
            except Exception as e:
                # One query failing costs that group of readings, not the pet:
                # carry the last ones over if there are any.
                capture_exception(e)
                if old is not None:
                    p.copyAttrs(old, attrs)
        LOGGER.debug(f"Adding Pet: {p._name} with Device: {p._device._deviceId}")
        return p

    @staticmethod
    def _periods(json):
        return json['dailyStat'], json['weeklyStat'], json['monthlyStat']

    def _loadBases(self, households):
        bases = []
        for house in households:
            for base in (house.get('household') or {}).get('bases') or []:
                try:
                    b = FiBase(base['baseId'])
                    b.setBaseDetailsJSON(base)
                    LOGGER.debug(f"Adding Base: {b._name} Online: {b._online}")
                    bases.append(b)
                except Exception as e:
                    capture_exception(e)
                    LOGGER.warning(f"Could not load base {base.get('baseId')}, skipping it: {e}")
        return bases

    def updatePetObject(self, petObj):
        try:
            petId = petObj.petId
            count = 0
            for p in self.pets:
                if p.petId == petId:
                    self._pets.pop(count)
                    self._pets.append(petObj)
                    LOGGER.debug(f"Updating Existing Pet: {petId}")
                    break
                count = count + 1
        except Exception as e:
            capture_exception(e)

    # return the pet object based on petId
    def getPet(self, petId):
        try:
            for p in self.pets:
                if petId == p.petId:
                    return p
            # hass-tryfi: debug, not error. Home Assistant asks for a pet that
            # has left the account on every refresh, and errors filled the log.
            LOGGER.debug(f"Cannot find Pet: {petId}")
            return None
        except Exception as e:
            capture_exception(e)

    #refresh base details
    def updateBases(self):
        self._bases = self._loadBases(query.getBaseList(self._session))

    # return the pet object based on petId
    def getBase(self, baseId):
        try:
            for b in self.bases:
                if baseId == b.baseId:
                    return b
            LOGGER.debug(f"Cannot find Base: {baseId}")
            return None
        except Exception as e:
            capture_exception(e)

    def update(self):
        # hass-tryfi: one households query for pets and bases, not two of the
        # same, and any failure to fetch it raises to the caller.
        households = query.getPetList(self._session)
        self._bases = self._loadBases(households)
        previous = {p.petId: p for p in self._pets}
        self._pets = self._loadPets(households, previous)

    @property
    def currentUser(self):
        return self._currentUser
    @property
    def pets(self):
        return self._pets
    @property
    def bases(self):
        return self._bases
    @property
    def username(self):
        return self._username
    @property
    def session(self):
        return self._session
    @property
    def cookies(self):
        return self._cookies
    @property
    def userID(self):
        return self._userID
    @property
    def session(self):
        return self._session

    # login to the api and get a session
    def login(self):
        error = None
        url = API_HOST_URL_BASE + API_LOGIN
        params={
                'email' : self._username,
                'password' : self._password,
            }
        
        LOGGER.debug(f"Logging into TryFi")
        try:
            response = self._session.post(url, data=params, timeout=query.TIMEOUT)
            response.raise_for_status()
            #validate if the response contains error or not
            try:
                error = response.json()['error']
            except Exception as e:
                #capture_exception(e)
                error = None
            #if error set or response is non-200
            if error or not response.ok:
                errorMsg = error['message']
                LOGGER.error(f"Cannot login, response: ({response.status_code}): {errorMsg} ")
                capture_exception(errorMsg)
                raise Exception("TryFiLoginError")
            
            #storing cookies but don't need them. Handled by session mgmt
            self._cookies = response.cookies
            #store unique userId from login for future use
            self._userId = response.json()['userId']
            self._sessionId = response.json()['sessionId']
            LOGGER.debug(f"Successfully logged in. UserId: {self._userId}")
        except requests.RequestException as e:
            LOGGER.error(f"Cannot login, error: ({e})")
            raise e
