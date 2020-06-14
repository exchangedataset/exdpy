from typing import Optional, List, Iterable, Text, Tuple, TypedDict, MutableMapping, Mapping, Iterator
from multiprocessing import Pool

from .common import TextLine, Filter, AnyDateTime, APIKey, LineType, _REGEX_NAME, _check_filter, _convert_any_date_time_to_nanosec, _convert_any_minute_to_minute, _ClientSetting, _setup_client_setting, _convert_nanosec_to_minute
from .constants import FILTER_DEFAULT_BUFFER_SIZE, DOWNLOAD_BATCH_SIZE
from .http import _filter, _snapshot, Snapshot

class RawRequest:
    """Replays market data in raw format.

    You can pick the way to read the response:
    - :func:`download` to immidiately start downloading the whole response as one array in the synchronous way.
    - :func:`stream` to return iterable object yields line by line.
    """

    """Send request and download response in an array.
    
    :param concurrency: Number of concurrency to download data from HTTP Endpoints
    :returns: List of lines
    """
    def download(self, concurrency: int = DOWNLOAD_BATCH_SIZE) -> List[TextLine]:
        pass

    """Send request to server and read response by streaming.
    
    Returns Iterable object yields response line by line.

    Iterator has a internal buffer, whose size can be specified by `buffer_size` parameter,
    and will try to fill the buffer by downloading neccesary data.

    Iterator yields immidiately if a line is bufferred, waits for download if not available.

    Downloading is multi-threaded and done concurrently.

    **Please note that buffering won't start by calling this function,**
    **calling :func:`__iter__` of a returned iterable will.**

    :param buffer_size: Optional. Desired buffer size to store streaming data. One Shard is equivalent to one minute.
    :returns: Instance of class implements `Iterable` from which iterator that yields response line by line from buffer can be obtained.
    """
    def stream(self, buffer_size: int = FILTER_DEFAULT_BUFFER_SIZE) -> Iterable[TextLine]:
        pass

class _ShardsLineIterator(Iterator):
    def __init__(self, shards: List[List[TextLine]]):
        self._shards = shards
        self._shard_pos = 0
        self._position = 0

    def __next__(self):
        while (self._shard_pos < len(self._shards) and len(self._shards[self._shard_pos]) < self._position):
            # this shard is all read
            self._shard_pos += 1
            self._position = 0
        if self._shard_pos == len(self._shards):
            raise StopIteration
        # return line
        line = self._shards[self._shard_pos][self._position]
        self._position += 1
        return line

def _convert_snapshots_to_lines(exchange: Text, snapshots: List[Snapshot]) -> List[TextLine]:
    # exchange: Text
    ## type: LineType
    # timestamp: int
    # channel: Text
    # message: Text
    return list(map(lambda snapshot : TextLine(
        exchange,
        LineType.MESSAGE,
        snapshot.timestamp,
        snapshot.channel,
        snapshot.snapshot,
    ), snapshots))

def _runner_download_all_shards(params: Tuple):
    op: Text = params[0]
    if op == 'snapshot':
        exchange = params[2]
        return _convert_snapshots_to_lines(exchange, _snapshot(*params[1:]))
    elif op == 'filter':
        return _filter(*params[1:])
    else:
        raise ValueError('Unknown operation: %s' % op)

def _download_all_shards(client_setting: _ClientSetting, filt: Filter, start: int, end: int, formt: Optional[Text], concurrency: int) -> Mapping[Text, List[List[TextLine]]]:
    # prepare parameters for multithread runners to fetch shards
    tasks: List[Tuple] = []
    for (exchange, channels) in filt.items():
        # take snapshot of channels at the begginging of data
        tasks.append(('snapshot', client_setting, exchange, channels, start, formt))

        # call Filter HTTP Endpoint to get the rest of data
        start_minute = _convert_nanosec_to_minute(start)
        # excluding exact end nanosec
        end_minute = _convert_nanosec_to_minute(end-1)
        # minute = [start minute, end minute]
        for minute in range(start_minute, end_minute+1):
            tasks.append(('filter', client_setting, exchange, channels, minute, formt, start, end))

    # download them in multithread way
    pool = Pool(processes=concurrency)
    # sequence is preserved after mapping, this thread will be blocked until all tasks are done
    try:
        mapped: List[List[TextLine]] = pool.map(_runner_download_all_shards, tasks)
    finally:
        # this ensures pool will stop all tasks even if any one of them generates error
        pool.terminate()

    exc_shards: MutableMapping[Text, List[List[TextLine]]] = {}
    for i in range(len(mapped)):
        exchange = tasks[i][2]
        if exchange not in exc_shards:
            # initialize list for an exchange
            exc_shards[exchange] = []
        exc_shards[exchange].append(mapped[i])

    return exc_shards

class _RawRequestImpl(RawRequest):
    def __init__(self, client_setting: _ClientSetting, filt: Filter, start: AnyDateTime, end: AnyDateTime, formt: Optional[Text]):
        self._setting = client_setting
        _check_filter(filt)
        self._filter = filt
        self._start = _convert_any_date_time_to_nanosec(start)
        self._end = _convert_any_date_time_to_nanosec(end)
        if formt is not None:
            if not isinstance(formt, str):
                raise TypeError('Parameter "formt" must be a string')
            if not _REGEX_NAME.match(formt):
                raise ValueError('Parameter "formt" must be an valid string')
        self._format = formt

    def download(self, concurrency: int = DOWNLOAD_BATCH_SIZE) -> List[TextLine]:
        mapped = _download_all_shards(self._setting, self._filter, self._start, self._end, self._format, concurrency)

        # prepare shards line iterator for all exchange
        IteratorAndLastLine = TypedDict('IteratorAndLastLine', {'iterator': _ShardsLineIterator, 'last_line': TextLine})
        states: MutableMapping[Text, IteratorAndLastLine] = {}
        exchanges: List[Text] = []
        for (exchange, shards) in mapped.items():
            itr = _ShardsLineIterator(shards)
            try:
                nxt = next(itr)
                exchanges.append(exchange)
                states[exchange] = {
                    'iterator': itr,
                    'last_line': nxt,
                }
            except StopIteration:
                # data for this exchange is empty, ignore
                pass

        # it needs to process lines so that it becomes a single array
        array: List[TextLine] = []
        while (len(exchanges) > 0):
            # have to set initial value to calculate minimum value
            argmin = len(exchanges) - 1
            tmpLine = states[exchanges[argmin]]['last_line']
            mi = tmpLine.timestamp
            # must start from the end because it needs to remove its elements
            for i in range(len(exchanges) - 2, 0, -1):
                exchange = exchanges[i]
                line = states[exchange]['last_line']
                if line.timestamp < mi:
                    mi = line.timestamp
                    argmin = i

            state = states[exchanges[argmin]]
            # append the line
            array.append(state['last_line'])
            # find the next line for this exchange, if does not exist, remove the exchange
            try:
                nxt = next(state['iterator'])
                state['last_line'] = nxt
            except:
                # next line is absent
                exchanges.remove(exchange)
        
        return array

    def stream(self, buffer_size: int = FILTER_DEFAULT_BUFFER_SIZE) -> Iterable[TextLine]:
        pass

def raw(apikey: APIKey, timeout: float, filt: Filter, start: AnyDateTime, end: AnyDateTime, formt: Optional[Text] = None) -> RawRequest:
    return _RawRequestImpl(_setup_client_setting(apikey, timeout), filt, start, end, formt)
