from typing import Text, TypedDict, List, Optional

from .constants import CLIENT_DEFAULT_TIMEOUT
from .common import _setup_client_setting, Filter, AnyDateTime
from .raw import _RawRequestImpl, RawRequest
from .http import HTTPModule

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
        return self._http

    def raw(self, filter: Filter, start: AnyDateTime, end: AnyDateTime, formt: Optional[Text] = None) -> RawRequest:
        return _RawRequestImpl(self._setting, filter, start, end, formt)

    # def replay(self) -> ReplayRequestBuilder:
    #     pass
