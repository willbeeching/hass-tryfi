"""Local stand-ins for the error-reporting calls pytryfi makes.

Upstream sent these, and every ERROR record in the host process, to a
third-party service whose key belongs to the library author. Here they go to
this package's own logger at debug level and nowhere else, so an exception the
library swallows can still be found by turning on debug logging for the
integration.

The call sites are left as upstream wrote them so the vendored code stays easy
to compare with the commit it came from.
"""

import logging

LOGGER = logging.getLogger(__name__)


def capture_exception(error=None, *args, **kwargs):
    if isinstance(error, BaseException):
        LOGGER.debug("pytryfi swallowed an exception: %s", error, exc_info=error)
    else:
        LOGGER.debug("pytryfi swallowed an error: %s", error)


def capture_message(message=None, *args, **kwargs):
    LOGGER.debug("pytryfi message: %s", message)
