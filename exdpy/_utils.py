import re
from .common import AnyDateTime, AnyMinute
from datetime import datetime

REGEX_NAME = re.compile(r'^[a-zA-Z0-9-]+$')
REGEX_APIKEY = re.compile(r'^[A-Za-z0-9\-_]+$')

def convert_any_date_time_to_nanosec(any_date_time: AnyDateTime):
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

def convert_any_minute_to_minute(any_minute: AnyMinute):
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
