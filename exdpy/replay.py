from typing import Text, List, MutableMapping, Set, Mapping, Any, Optional, Iterator, Iterable, cast
import json

from .constants import DEFAULT_BUFFER_SIZE, CLIENT_DEFAULT_TIMEOUT
from .common import TextLine, MappingLine, LineType, APIKey, Filter, AnyDateTime, _ClientSetting, _setup_client_setting, _check_filter, _convert_any_date_time_to_nanosec
from .raw import _RawRequestImpl



class ReplayRequest:
    def download(self) -> List[MappingLine]:
        """Send requests and download responses in an array.

        All data will be lost if there was an error while downloading
        any part of the request, including when your API-key quota runs out.

        :returns: List of lines
        """
        pass

    def stream(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> Iterable[MappingLine]:
        """Send requests to the server and read responses by streaming.
        
        Returns :class:`Iterable` object yields a response line by line.
        Can be iterated by for-in sentence.
        The iterator yields a line immidiately if it is bufferred, but waits for it to be downloaded if not available.
        
        **Please note that buffering won't start by calling this function,**
        **calling :func:`__iter__` of a returned iterable will.**
        
        Higher responsiveness than :func:`download` is expected as it does not have to wait for
        the entire date to be downloaded.

        :param buffer_size: Optional. Desired buffer size to store streaming data. One shard is equivalent to one minute.
        :returns: Instance of class implements :class:`Iterable` from which iterator that yields response line by line from buffer can be obtained.
        """
        pass


ReplayMessageDefinition = Mapping[Text, Text]

class _RawLineProcessor:
    def __init__(self):
        self._defs: MutableMapping[Text, MutableMapping[Text, ReplayMessageDefinition]] = {}

    def process_raw_line(self, line: TextLine) -> Optional[MappingLine]:
        # convert only if needed to
        if line.type == LineType.START:
            # reset definition
            self._defs[line.exchange] = {}
        if line.type != LineType.MESSAGE:
            return cast(MappingLine, line)
        
        exchange = line.exchange
        # those variables are always available since type == msg
        channel = cast(Text, line.channel)
        message = cast(Text, line.message)

        if exchange not in self._defs:
            # this is the first line for this exchange
            self._defs[exchange] = {}
        if channel not in self._defs[exchange]:
            self._defs[exchange][channel] = json.loads(message)
            return None

        msgObj = json.loads(message)

        # type conversion according to the received definition
        defn: Mapping[Text, Any] = self._defs[exchange][channel]
        for name, typ in defn.items():
            if (typ == 'timestamp' or typ == 'duration') and msgObj[name] is not None:
                # convert timestamp type parameter into int
                msgObj[name] = int(msgObj[name], base=10)

        # exchange: Text
        ## type: LineType
        # timestamp: int
        # channel: Text
        # message: Mapping
        return MappingLine(
            exchange,
            line.type,
            line.timestamp,
            line.channel,
            msgObj,
        )

class _ReplayStreamIterator(Iterator[MappingLine]):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: int,
        end: int,
        buffer_size: int,
    ):
        self._setting = client_setting
        req = _RawRequestImpl(
            client_setting,
            filt,
            start,
            end,
            'json',
        )
        self._raw_itr: Iterator[TextLine] = iter(req.stream(buffer_size))
        self._processor = _RawLineProcessor()

    def __next__(self):
        while True:
            try:
                line = next(self._raw_itr)
            except StopIteration:
                raise StopIteration

            processed = self._processor.process_raw_line(line)
            if processed is None:
                continue
            return processed

class _ReplayStreamIterable(Iterable[MappingLine]):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: int,
        end: int,
        buffer_size: int,
    ):
        self._setting = client_setting
        self._filter = filt
        self._start = start
        self._end = end
        self._buffer_size = buffer_size

    def __iter__(self):
        return _ReplayStreamIterator(self._setting, self._filter, self._start, self._end, self._buffer_size)


class _ReplayRequestImpl(ReplayRequest):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: AnyDateTime,
        end: AnyDateTime,
    ):
        self._setting = client_setting
        _check_filter(filt, 'filt')
        self._filter = filt
        self._start = _convert_any_date_time_to_nanosec(start)
        self._end = _convert_any_date_time_to_nanosec(end)
        if self._start >= self._end:
            raise ValueError('Parameter "start" cannot be equal or bigger than "end"')
    
    def download(self) -> List[MappingLine]:
        req = _RawRequestImpl(
            self._setting,
            self._filter,
            self._start,
            self._end,
            'json',
        )
        array = req.download()
        result: List[MappingLine] = []
        processor = _RawLineProcessor()

        for i in range(len(array)):
            processed = processor.process_raw_line(array[i])
            if processed is None:
                continue
            result.append(processed)
            
        return result

    def stream(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> Iterable[MappingLine]:
        return _ReplayStreamIterator(self._setting, self._filter, self._start, self._end, buffer_size)

def replay(
    apikey: APIKey,
    filt: Filter,
    start: AnyDateTime,
    end: AnyDateTime,
    timeout: float = CLIENT_DEFAULT_TIMEOUT,
):
    return _ReplayRequestImpl(
        _setup_client_setting(apikey, timeout),
        filt,
        start,
        end,
    )
