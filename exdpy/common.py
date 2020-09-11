from typing import Text, Union, Generic, NamedTuple, TypeVar, List, Optional, Mapping, TypedDict
from enum import Enum
from datetime import datetime
import re

_REGEX_NAME = re.compile(r'^[a-zA-Z0-9_]+$')
_REGEX_APIKEY = re.compile(r'^[A-Za-z0-9\-_]+$')

APIKey = Text

AnyDateTime = Union[int, Text, datetime]

def _convert_any_date_time_to_nanosec(any_date_time: AnyDateTime) -> int:
    if isinstance(any_date_time, int):
        # already in nanosec
        return any_date_time
    elif isinstance(any_date_time, str):
        # Z indicating UTC timezone is not supported by fromisoformat
        # however, +00:00 is supported
        any_date_time = any_date_time.replace('Z', '+00:00')
        # convert it to datetime using iso format
        any_date_time = datetime.fromisoformat(any_date_time)
    
    if isinstance(any_date_time, datetime):
        timestamp = any_date_time.timestamp()
        # split timestamp in seconds in float into seconds part and under seconds part
        # this is to prevent precision issue
        seconds = int(timestamp)
        nanosecs = int((timestamp - seconds) * 1_000_000_000)

        return seconds * 1_000_000_000 + nanosecs
    else:
        raise TypeError('type "%s" is not supported for AnyDateTime', type(any_date_time))

AnyMinute = Union[int, Text, datetime]

def _convert_any_minute_to_minute(any_minute: AnyMinute) -> int:
    if isinstance(any_minute, int):
        # already in minute
        return any_minute
    elif isinstance(any_minute, str):
        # convert it to datetime using iso format
        any_minute = any_minute.replace('Z', '+00:00')
        any_minute = datetime.fromisoformat(any_minute)

    if isinstance(any_minute, datetime):
        timestamp = any_minute.timestamp()

        # convert seconds to minutes
        return int(timestamp / 60)
    else:
        raise TypeError('type "%s" is not supported for AnyMinute', type(any_minute))

def _convert_nanosec_to_minute(nanosec: int) -> int:
    return nanosec // 60_000_000_000

class LineType(Enum):
    """Enum of Line Type.
    
    Line Type shows what type of a line is, such as message line or start line.

    Lines with different types contain different information and have to be treated accordingly.
    """
    """Message Line Type.
    
    Contains message sent from exchanges' server.
    This is the most usual Line Type.
    """
    MESSAGE = 'msg'
    """Send Line Type.
    
    Message send from one of our client when recording.
    """
    SEND = 'send'
    """Start Line Type
    
    Indicates the first line in the continuous recording.
    """
    START = 'start'
    """End Line Type.
    
    Indicates the end line in the continuous recording.
    """
    END = 'end'
    """Error Line Type
    
    Used when error occurrs on recording.
    
    Used in both server-side error and client-side (our client who receive WebSocket data) error.
    """
    ERROR = 'err'

_LineTypeValueOf: Mapping[Text, LineType] = {
    'msg': LineType.MESSAGE,
    'send': LineType.SEND,
    'start': LineType.START,
    'end': LineType.END,
    'err': LineType.ERROR,
}

class MappingLine(NamedTuple):
    """See :class:`TextLine`."""
    exchange: Text
    type: LineType
    timestamp: int
    channel: Optional[Text]
    message: Optional[Mapping]

class TextLine(NamedTuple):
    """Data structure of a single line from a response.
    
    `exchange`, `type` and `timestamp` is always present, **but `channel` or `message` is not.**
    This is because with certain `type`, a line might not contain `channel` or `message`, or both.
    """
    """Name of exchange from which this line is recorded."""
    exchange: Text
    """If `type === LineType.MESSAGE`, then a line is a normal message.
    All of value are present.
    You can get an assosiated channel by `channel`, and its message by `message`.

    If `type === LineType.SEND`, then a line is a request server sent when the dataset was
    recorded.
    All of value are present, though you can ignore this line.

    If `type === LineType.START`, then a line marks the start of new continuous recording of the
    dataset.
    Only `channel` is not present. `message` is the URL which used to record the dataset.
    You might want to initialize your work since this essentially means new connection to
    exchange's API.

    If `type === LineType.END`, then a line marks the end of continuous recording of the dataset.
    Other than `type` and `timestamp` are not present.
    You might want to perform some functionality when the connection to exchange's API was lost.

    If `type === LineType.ERROR`, then a line contains error message when recording the dataset.
    Only `channel` is not present. `message` is the error message.
    You want to ignore this line.
    """
    type: LineType
    """Timestamp in nano seconds of this line was recorded.

    Timestamp is in unixtime-compatible format (unixtime * 10^9 + nanosec-part).
    Timezone is UTC.
    """
    timestamp: int
    """Channel name which this line is associated with.
    Could be `None` according to `type`.
    """
    channel: Optional[Text]
    """Message.
    Could be `None` accoring to `type`.
    """
    message: Optional[Text]

Shard = List[TextLine]

Filter = Mapping[Text, List[Text]]

def _check_filter(filter: Filter, argname: Text):
    for (exchange, channels) in filter.items():
        if not isinstance(exchange, str):
            raise TypeError('%s: Name of exchange must be an string', argname)
        if not _REGEX_NAME.match(exchange):
            raise ValueError('%s: Name of exchange must be an valid string: %s' % (argname, exchange))
        for ch in channels:
            if not isinstance(ch, str):
                raise TypeError('%s: Name of channel must be an string' % argname)
            if not _REGEX_NAME.match(ch):
                raise ValueError('%s: Name of channel must be an valid string: %s' % (argname, ch))

class _ClientSetting(TypedDict):
    """Settings for :class:`Client`"""
    apikey: APIKey
    timeout: float

def _setup_client_setting(apikey: Text, timeout: float) -> _ClientSetting:
    if apikey is None:
        raise TypeError('parameter "apikey" must be specified')
    if not isinstance(apikey, str):
        raise TypeError('parameter "apikey" must be an string')
    if not _REGEX_APIKEY.match(apikey):
        raise ValueError('parameter "apikey" must be an valid API-key')
    if not isinstance(timeout, float):
        raise TypeError('parameter "timeout" must be an float')
    if timeout < 0:
        raise ValueError('parameter "timeout" must not be negative')

    return {
        'apikey': apikey,
        'timeout': timeout,
    }
