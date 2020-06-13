from typing import Text, Union, Generic, NamedTuple, TypeVar, List, Optional, Mapping
from enum import Enum
from datetime import datetime

AnyMinute = Union[int, Text, datetime]
AnyDateTime = Union[int, Text, datetime]
APIKey = Text

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

LineTypeValueOf: Mapping[Text, LineType] = {
    'msg': LineType.MESSAGE,
    'send': LineType.SEND,
    'start': LineType.START,
    'end': LineType.END,
    'err': LineType.ERROR,
}

T = TypeVar('T')

class TextLine(NamedTuple, Generic[T]):
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

