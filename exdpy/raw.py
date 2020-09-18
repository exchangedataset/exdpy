from typing import Optional, List, Iterable, Text, Tuple, TypedDict, MutableMapping, Mapping, Iterator, Deque
from multiprocessing import Pool, Process, Pipe, Queue
from multiprocessing.connection import Connection
from queue import Empty as QueueEmptyError
from collections import deque

from .constants import DEFAULT_BUFFER_SIZE, DOWNLOAD_CONCURRENCY, CLIENT_DEFAULT_TIMEOUT
from .common import Shard, TextLine, Filter, AnyDateTime, APIKey, LineType, _REGEX_NAME, _check_filter, _convert_any_date_time_to_nanosec, _convert_any_minute_to_minute, _ClientSetting, _setup_client_setting, _convert_nanosec_to_minute
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
    def download(self, concurrency: int = DOWNLOAD_CONCURRENCY) -> List[TextLine]:
        pass

    """Send requests to the server and read the response by streaming.
    
    Returns Iterable object yields line by line.

    Iterator has a internal buffer, whose size can be specified by `buffer_size` parameter,
    and will try to fill the buffer by downloading neccesary data.

    Iterator yields immidiately if a line is bufferred, waits for download if not available.

    Downloading is multi-processed and done concurrently.

    **Please note that buffering won't start by calling this function,**
    **calling :func:`__iter__` of a returned iterable will.**

    :param buffer_size: Optional. Desired buffer size to store streaming data. One Shard is equivalent to one minute.
    :returns: Instance of class implements :class:`Iterable` from which iterator that yields response line by line from buffer can be obtained.
    """
    def stream(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> Iterable[TextLine]:
        pass



def _convert_snapshots_to_lines(exchange: Text, snapshots: List[Snapshot]) -> Shard:
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



def _runner_exchange_iterator_download_shard(error_queue: Queue, pipe_send: Connection, op: Text, params: Tuple):
    try:
        if op == 'snapshot':
            exchange = params[1]
            shard = _convert_snapshots_to_lines(exchange, _snapshot(*params))
        elif op == 'filter':
            shard = _filter(*params)
        else:
            raise ValueError('Unknown operation: %s' % op)
        # finally, send back shard through pipe
        pipe_send.send(shard)
    except BaseException as e:
        # report error
        error_queue.put_nowait(e)
        raise e

class _ExchangeStreamShardIterator(Iterator[Shard]):
    def __init__(self,
        client_setting: _ClientSetting,
        exchange: Text,
        channels: List[Text],
        start: int,
        end: int,
        formt: Optional[Text],
        buffer_size: int,
    ):
        self._setting = client_setting
        self._exchange = exchange
        self._channels = channels
        self._start = start
        self._end = end
        self._format = formt
        self._next_download_minute = start_minute = _convert_nanosec_to_minute(start)
        # end is exclusive
        self._end_minute = end_minute = _convert_nanosec_to_minute(end - 1)
        # process management queue, tuple of process and pipe connection (receive only)
        # used in fifo way
        self._queue: Deque[Tuple[Process, Connection]] = deque(maxlen=buffer_size)
        # to receive error from child process
        self._error_queue: Queue = Queue()
        # fill the buffer
        self._download_snapshot()
        for i in range(min(buffer_size - 1, end_minute - start_minute + 1)):
            self._download_filter()

    def _download_snapshot(self):
        # creating pipe for 
        pipe_recv, pipe_send = Pipe(duplex=False)
        proc = Process(target=_runner_exchange_iterator_download_shard, args=(
            self._error_queue,
            pipe_send,
            'snapshot',
            (
                self._setting,
                self._exchange,
                self._channels,
                self._start,
                self._format,
            )
        ))
        # start new process
        proc.start()
        # add process and receive end of pipe into a query
        self._queue.append((proc, pipe_recv))

    def _download_filter(self):
        pipe_recv, pipe_send = Pipe(duplex=False)
        proc = Process(target=_runner_exchange_iterator_download_shard, args=(
            self._error_queue,
            pipe_send,
            'filter',
            (
                self._setting,
                self._exchange,
                self._channels,
                self._next_download_minute,
                self._format,
                self._start,
                self._end,
            )
        ))
        proc.start()
        self._queue.append((proc, pipe_recv))
        # increment minute
        self._next_download_minute += 1

    def __next__(self) -> Shard:
        if len(self._queue) <= 0:
            # no bufferred shard in queue
            raise StopIteration

        # pop from left, because fifo
        proc, pipe_recv = self._queue.popleft()
        # wait until receiving a shard from pipe
        shard: Shard = pipe_recv.recv()
        # receive error if stored
        try:
            sub_err = self._error_queue.get_nowait()
            try:
                proc.terminate()
                proc.join()
                self._close()
            except:
                pass
            raise RuntimeError(sub_err)
        except QueueEmptyError:
            pass
        # this will prevent child process from becoming a zombie process
        proc.join()
        # download next shard if it should
        if self._next_download_minute <= self._end_minute:
            self._download_filter()
        return shard

    def _close(self):
        """terminate all child process"""
        while len(self._queue) > 0:
            proc, _ = self._queue.pop()
            proc.terminate()
            # prevent zombie process
            proc.join()

    def __del__(self):
        """terminate all child processes if this instance is being garbadge collected"""
        self._close()

class _ExchangeStreamIterator(Iterator[TextLine]):
    def __init__(self,
        client_setting: _ClientSetting,
        exchange: Text,
        channels: List[Text],
        start: int,
        end: int,
        formt: Optional[Text],
        buffer_size: int,
    ):
        self._setting = client_setting
        self._exchange = exchange
        self._channels = channels
        self._start = start
        self._end = end
        self._format = formt
        self._buffer_size = buffer_size
        # iterator and states
        self._shard_iterator = _ExchangeStreamShardIterator(
            client_setting,
            exchange,
            channels,
            start,
            end,
            formt,
            buffer_size,
        )
        self._shard: Optional[Shard] = None
        self._position = 0

    def __next__(self) -> TextLine:
        if self._shard is None:
            # get very first shard
            try:
                self._shard = next(self._shard_iterator)
            except StopIteration:
                # shard iterator empty
                raise StopIteration
        while len(self._shard) <= self._position:
            try:
                self._shard = next(self._shard_iterator)
                self._position = 0
            except:
                # reached the last line
                raise StopIteration
        
        # return the line
        line = self._shard[self._position]
        self._position += 1
        return line

class _RawStreamIterator(Iterator[TextLine]):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: int,
        end: int,
        formt: Optional[Text],
        buffer_size: int,
    ):
        self._setting = client_setting
        # states
        states: MutableMapping[Text, _IteratorAndLastLine] = {}
        exchanges: List[Text] = []
        for (exchange, channels) in filt.items():
            iterator = _ExchangeStreamIterator(
                client_setting,
                exchange,
                channels,
                start,
                end,
                formt,
                buffer_size,
            )
            try:
                nxt = next(iterator)
                states[exchange] = {
                    'iterator': iterator,
                    'last_line': nxt,
                }
                exchanges.append(exchange)
            except StopIteration:
                # ignore this exchange
                pass
        self._states: Mapping[Text, _IteratorAndLastLine] = states
        self._exchanges: List[Text] = exchanges

    def __next__(self) -> TextLine:
        if (len(self._exchanges) == 0):
            # all lines returned
            raise StopIteration

        # return the line that has the smallest timestamp of all shards of each exchange
        argmin = 0
        mi = self._states[self._exchanges[argmin]]['last_line'].timestamp
        for i in range(1, len(self._exchanges)):
            last_line = self._states[self._exchanges[i]]['last_line']
            if last_line.timestamp < mi:
                argmin = i
                min = last_line.timestamp
        
        exchange = self._exchanges[argmin]
        state = self._states[exchange]
        line = state['last_line']
        try:
            nxt = next(state['iterator'])
            state['last_line'] = nxt
        except StopIteration:
            # remove from exchanges list
            self._exchanges.remove(exchange)

        return line

class _RawStreamIterable(Iterable[TextLine]):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: int,
        end: int,
        formt: Optional[Text],
        buffer_size: int,
    ):
        self._setting = client_setting
        self._filter = filt
        self._start = start
        self._end = end
        self._format = formt
        self._buffer_size = buffer_size

    def __iter__(self) -> Iterator[TextLine]:
        return _RawStreamIterator(
            self._setting,
            self._filter,
            self._start,
            self._end,
            self._format,
            self._buffer_size,
        )

class _ShardsLineIterator(Iterator):
    def __init__(self, shards: List[Shard]):
        self._shards = shards
        self._shard_pos = 0
        self._position = 0

    def __next__(self):
        while (self._shard_pos < len(self._shards) and len(self._shards[self._shard_pos]) <= self._position):
            # this shard is all read
            self._shard_pos += 1
            self._position = 0
        if self._shard_pos == len(self._shards):
            raise StopIteration
        # return line
        line = self._shards[self._shard_pos][self._position]
        self._position += 1
        return line

_IteratorAndLastLine = TypedDict('_IteratorAndLastLine', {'iterator': Iterator, 'last_line': TextLine})

def _runner_download_shard(params: Tuple):
    op: Text = params[0]
    if op == 'snapshot':
        exchange = params[2]
        return _convert_snapshots_to_lines(exchange, _snapshot(*params[1:]))
    elif op == 'filter':
        return _filter(*params[1:])
    else:
        raise ValueError('Unknown operation: %s' % op)

class _RawRequestImpl(RawRequest):
    def __init__(self,
        client_setting: _ClientSetting,
        filt: Filter,
        start: AnyDateTime,
        end: AnyDateTime,
        formt: Optional[Text]
    ):
        self._setting = client_setting
        _check_filter(filt, "filt")
        # copy filter
        self._filter = dict()
        for (exc, chs) in filt.items():
            self._filter[exc] = chs.copy()
        
        self._start = _convert_any_date_time_to_nanosec(start)
        self._end = _convert_any_date_time_to_nanosec(end)
        if self._start >= self._end:
            raise ValueError('Parameter "start" cannot be equal or bigger than "end"')
        if formt is not None:
            if not isinstance(formt, str):
                raise TypeError('Parameter "formt" must be a string')
            if not _REGEX_NAME.match(formt):
                raise ValueError('Parameter "formt" must be an valid string')
        self._format = formt

    def _download_all_shards(self, concurrency: int) -> Mapping[Text, List[List[TextLine]]]:
        # prepare parameters for multiprocess runners to fetch shards
        tasks: List[Tuple] = []
        for (exchange, channels) in self._filter.items():
            # take snapshot of channels at the begginging of data
            tasks.append(('snapshot', self._setting, exchange, channels, self._start, self._format))

            # call Filter HTTP Endpoint to get the rest of data
            start_minute = _convert_nanosec_to_minute(self._start)
            # excluding exact end nanosec
            end_minute = _convert_nanosec_to_minute(self._end-1)
            # minute = [start minute, end minute]
            for minute in range(start_minute, end_minute+1):
                tasks.append(('filter', self._setting, exchange, channels, minute, self._format, self._start, self._end))

        # download them in multiprocess way
        # this ensures pool will stop all tasks even if any one of them generates error
        with Pool(processes=concurrency) as pool:
            # sequence is preserved after mapping, this thread will be blocked until all tasks are done
            mapped: List[Shard] = pool.map(_runner_download_shard, tasks)

        exc_shards: MutableMapping[Text, List[Shard]] = {}
        for i in range(len(tasks)):
            exchange = tasks[i][2]
            if exchange not in exc_shards:
                # initialize list for an exchange
                exc_shards[exchange] = []
            exc_shards[exchange].append(mapped[i])

        return exc_shards

    def download(self, concurrency: int = DOWNLOAD_CONCURRENCY) -> List[TextLine]:
        mapped = self._download_all_shards(concurrency)

        # prepare shards line iterator for all exchange
        states: MutableMapping[Text, _IteratorAndLastLine] = {}
        exchanges: List[Text] = []
        for exchange, shards in mapped.items():
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

        # process shards into single list
        result: List[TextLine] = []
        while len(exchanges) > 0:
            # Find the line that have the earliest timestamp
            # have to set the initial value to calculate the minimum value
            argmin = 0
            mi = states[exchanges[argmin]]['last_line'].timestamp
            for i in range(1, len(exchanges)):
                exchange = exchanges[i]
                line = states[exchange]['last_line']
                if line.timestamp < mi:
                    mi = line.timestamp
                    argmin = i

            state = states[exchanges[argmin]]
            # append the line
            result.append(state['last_line'])
            # find the next line for this exchange, if does not exist, remove the exchange
            try:
                nxt = next(state['iterator'])
                state['last_line'] = nxt
            except:
                # next line is absent
                exchanges.remove(exchange)
        
        return result

    def stream(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> Iterable[TextLine]:
        return _RawStreamIterable(
            self._setting,
            self._filter,
            self._start,
            self._end,
            self._format,
            buffer_size
        )

def raw(
    apikey: APIKey,
    filt: Filter,
    start: AnyDateTime,
    end: AnyDateTime,
    formt: Optional[Text] = None,
    timeout: float = CLIENT_DEFAULT_TIMEOUT,
) -> RawRequest:
    return _RawRequestImpl(
        _setup_client_setting(apikey, timeout),
        filt,
        start,
        end,
        formt
    )
