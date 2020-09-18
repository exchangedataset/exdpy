from typing import Text, TypedDict, List, Optional

from .constants import CLIENT_DEFAULT_TIMEOUT
from .common import _setup_client_setting, Filter, AnyDateTime
from .http import HTTPModule
from .raw import _RawRequestImpl, RawRequest
from .replay import _ReplayRequestImpl, ReplayRequest

class Client:
    def __init__(self,
        apikey: Text,
        timeout: float = CLIENT_DEFAULT_TIMEOUT,
    ):
        """Create :class:`Client` instance by given parameters.
        
        :param apikey: A string of API-key used to access HTTP Endpoint at the lower-level APIs.
        :param timeout: Timeout in seconds.
        """
        self._setting = _setup_client_setting(apikey, timeout)
        self._http = HTTPModule(self._setting)

    @property
    def http(self) -> HTTPModule:
        """Low-level http call module"""
        return self._http

    def raw(self, filt: Filter, start: AnyDateTime, end: AnyDateTime, formt: Optional[Text] = None) -> RawRequest:
        """Lower-level API that processes data from Exchangedataset HTTP-API and generate raw (close to exchanges' format) data."""
        return _RawRequestImpl(self._setting, filt, start, end, formt)

    def replay(self, filt: Filter, start: AnyDateTime, end: AnyDateTime) -> ReplayRequest:
        """Returns builder to create :class:`ReplayRequest` that replays market data."""
        return _ReplayRequestImpl(self._setting, filt, start, end)
