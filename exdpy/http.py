from __future__ import annotations
from typing import Text, Mapping, TypedDict, List, Generic, TypeVar, Union, NamedTuple, Optional, MutableMapping, Any
from enum import Enum
import requests
import gzip
import json
import re

from .constants import CLIENT_DEFAULT_TIMEOUT
from .common import AnyDateTime, AnyMinute, TextLine, LineType, LineTypeValueOf, APIKey
from ._utils import REGEX_NAME, convert_any_date_time_to_nanosec, convert_any_minute_to_minute
from .client import _ClientSetting, _setup_client_setting

def _download(client_setting: _ClientSetting, path: Text, params: Mapping[Text, Any]) -> Mapping:
    """Internal function to download from HTTP Endpoint.

    :param path: Path to resource.
    :param params: Query parameters.
    """

    req = requests.get('https://api.exchangedataset.cc/v1/%s' % path,
        params=params,
        headers={
            'Authorization': 'Bearer %s' % client_setting['apikey'],
        },
        timeout=client_setting['timeout'],
    )

    # check status code for any error
    if req.status_code != 200 and req.status_code != 404:
        error = None
        try:
            obj = req.json()
            if 'error' in obj:
                error = obj.error
            elif 'message' in obj:
                error = obj.message
            elif 'Message' in obj:
                error = obj.Message
        except:
            error = req.text
        raise RuntimeError('%s: Request failed: %d %s' % (path, req.status_code, error))

    # check content-type header
    content_type = req.headers['content-type']
    if content_type != 'text/plain':
        raise RuntimeError('Invalid response content-type, expected: \'text/plain\' got: \'%s\'' % content_type)

    if 'content-encoding' in req.headers:
        # content is possibly compressed
        content_encoding = req.headers['content-encoding']

        if content_encoding != 'gzip':
            raise RuntimeError('Found \'%s\' in Content-Encoding header, but it is not supported', content_encoding)

        return {
            'status_code': req.status_code,
            'content': gzip.decompress(req.content),
        }

    return {
        'status_code': req.status_code,
        'content': req.text,
    }

def _check_param_exchange(exchange: Text):
    if not isinstance(exchange, str):
        raise TypeError('parameter "exchange" must be an string')
    if not REGEX_NAME.match(exchange):
        raise ValueError('parameter "exchange" must be of alphabets or numbers or hyphen')

def _check_param_channels(channels: List[Text]):
    if not isinstance(channels, list):
        raise TypeError('parameter "channels" must be an list')
    for ch in channels:
        if not REGEX_NAME.match(ch):
            raise ValueError('parameter "channels" must be an list of string of alphabets or numbers or hyphen: "%s"' % ch)

def _filter(
    client_setting: _ClientSetting,
    exchange: Text,
    channels: List[Text],
    minute: AnyMinute,
    format: Optional[Text],
    start: Optional[AnyDateTime],
    end: Optional[AnyDateTime],
) -> List[TextLine]:
    """Internal function to call Filter HTTP Endpoint."""
    # check parameters
    _check_param_exchange(exchange)
    _check_param_channels(channels)

    # prepare query parameters
    params: MutableMapping[Text, Any] = {
        'channels': channels,
    }
    if format is not None:
        params['format'] = format
    if start is not None:
        params['start'] = start
    if end is not None:
        params['end'] = end

    # convert any minute into minutes
    minute_minute = convert_any_minute_to_minute(minute)

    # download from HTTP Endpoint
    res = _download(client_setting, 'filter/%s/%d' % (exchange, minute_minute), params)

    if res['status_code'] == 404:
        # 404, return empty list
        return list()

    # convert into line objects
    content: str = res['content']

    # split by line terminator
    lines = content.splitlines(False)
    # prepare list to store result
    result: List = [None] * len(lines)
    # convert lines
    for i in range(len(lines)):
        l = lines[i]
        lineTypeStr = l[:l.find('\t')]

        if lineTypeStr not in LineTypeValueOf:
            raise RuntimeError('Unknown line type: %s' % lineTypeStr)

        lineType = LineTypeValueOf[lineTypeStr]

        # exchange: Text
        ## type: LineType
        # timestamp: int
        # channel: Text
        # message: Text

        if lineType == LineType.MESSAGE or lineType == LineType.SEND:
            split = l.split('\t', 4)
            result[i] = TextLine(
                exchange,
                LineTypeValueOf[split[0]],
                int(split[1]),
                split[2],
                split[3],
            )
        elif lineType == LineType.START or lineType == LineType.END:
            split = l.split('\t', 3)
            result[i] = TextLine(
                exchange,
                LineTypeValueOf[split[0]],
                int(split[1]),
                split[2],
                None,
            )
        elif lineType == LineType.ERROR:
            split = l.split('\t', 2)
            result[i] = TextLine(
                exchange,
                LineTypeValueOf[split[0]],
                int(split[1]),
                None,
                None,
            )

    return result

class Snapshot(NamedTuple):
    """This dict holds a line from Snapshot HTTP Endpoint."""
    timestamp: int
    channel: Text
    snapshot: Text

def _snapshot(
    client_setting: _ClientSetting,
    exchange: Text,
    channels: List[Text],
    at: AnyDateTime,
    format: Optional[Text],
) -> List[Snapshot]:
    """Internal function to call Snapshot HTTP Endpoint."""
    # check parameter type and value
    _check_param_exchange(exchange)
    _check_param_channels(channels)
    
    # construct query parameters
    params: MutableMapping[Text, Union[Text, List[Text]]] = {
        'channels': channels,
    }
    if format is not None:
        params['format'] = format

    # convert 'at' parameter into nanosec
    at_nanosec = convert_any_date_time_to_nanosec(at)

    # request to HTTP Endpoint
    res = _download(client_setting, 'snapshot/%s/%d' % (exchange, at_nanosec), params)
    content: str = res['content']

    # split by line terminator
    lines = content.splitlines(False)
    # prepare list to store result
    result: List = [None] * len(lines)
    for i in range(len(lines)):
        split = lines[i].split('\t')
        result[i] = Snapshot(
            int(split[0]),
            split[1],
            split[2],
        )

    return result

class HTTPModule:
    def __init__(self, client_setting: _ClientSetting):
        self._client_setting = client_setting
        
    def filter(self,
        exchange: Text,
        channels: List[Text],
        minute: AnyMinute,
        format: Optional[Text] = None,
        start: Optional[AnyDateTime] = None,
        end: Optional[AnyDateTime] = None,
    ) -> List[TextLine]:
        """Sends a request to Filter HTTP Endpoint with given parameter synchronously.

        :param exchange: Name of exchange.
        :param channels: List of name of channels.
        :param minute: Target minutes in UNIX time.
        :param format: Name of format to get response in.
        :param start: Minimum time including the time to filter-in lines in nano second UNIX time.
        :param end: Maximum time excluding the time to filter-in lines in nano second UNIX time.
        :returns: List of lines as an response.
        """

        return _filter(self._client_setting, exchange, channels, minute, format, start, end)

    def snapshot(self,
        exchange: Text,
        channels: List[Text],
        at: AnyDateTime,
        format: Text = None,
    ) -> List[Snapshot]:
        """Sends a request to Snapshot HTTP Endpoint with given parameter synchronously.
        
        :parameter 
        """
        return _snapshot(self._client_setting, exchange, channels, at, format)

def filter(
    apikey: APIKey,
    exchange: Text,
    channels: List[Text],
    minute: AnyMinute,
    format: Optional[Text] = None,
    start: Optional[AnyDateTime] = None,
    end: Optional[AnyDateTime] = None,
    timeout: float = CLIENT_DEFAULT_TIMEOUT,
):
    """Sends a request to Filter HTTP Endpoint.
    See :class:`Client`.:func:`filter`.

    :param apikey: API-key used to connect HTTP Endpoint.
    :param timeout: Optional. Connection timeout in seconds.
    """
    return _filter(
        _setup_client_setting(apikey, timeout),
        exchange,
        channels,
        minute,
        format,
        start,
        end
    )

def snapshot(
    apikey: APIKey,
    exchange: Text,
    channels: List[Text],
    at: AnyDateTime,
    format: Optional[Text] = None,
    timeout: float = CLIENT_DEFAULT_TIMEOUT,
):
    """Sends a request to Snapshot HTTP Endpoint.
    See :class:`Client`.:func:`snapshot`.

    :param apikey: API-key used to connect HTTP Endpoint.
    :param timeout: Optional. Connection timeout in seconds.
    """
    return _snapshot(
        _setup_client_setting(apikey, timeout),
        exchange,
        channels,
        at,
        format,
    )
