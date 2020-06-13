from typing import Text, TypedDict

from ._utils import REGEX_APIKEY

APIKey = Text

class _ClientSetting(TypedDict):
    """Settings for :class:`Client`"""
    apikey: APIKey
    timeout: float

def _setup_client_setting(apikey: Text, timeout: float) -> _ClientSetting:
    if apikey is None:
        raise TypeError('parameter "apikey" must be specified')
    if not isinstance(apikey, str):
        raise TypeError('parameter "apikey" must be an string')
    if not REGEX_APIKEY.match(apikey):
        raise ValueError('parameter "apikey" must be an valid API-key')
    if not isinstance(timeout, float):
        raise TypeError('parameter "apikey" must be an float')

    return {
        'apikey': apikey,
        'timeout': timeout,
    }

from .http import HTTPModule

class Client:
    def __init__(self,
        apikey: Text,
        timeout: float = 10.0,
    ):
        """Create :class:`Client` instance by given parameters.
        
        :param apikey: A string of API-key used to access HTTP Endpoint at the lower-level APIs.
        :param timeout: Connection timeout in seconds.
        """
        self._setting = _setup_client_setting(apikey, timeout)
        self._http = HTTPModule(self._setting)

    @property
    def http(self) -> HTTPModule:
        return self._http

    # def raw(self) -> RawRequest:
    #     pass

    # def replay(self) -> ReplayRequestBuilder:
    #     pass
