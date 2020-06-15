import exdpy

cli = exdpy.Client(apikey='demo')
req = cli.replay({
        'bitmex': ['orderBookL2_XBTUSD']
    },
    '2020-01-01 00:00:00Z',
    '2020-01-01 00:10:00Z',
)

def test_replay_download():
    lines = req.download()
    assert len(lines) != 0
    for i in range(len(lines)):
        assert type(lines[i].exchange) == str
        assert type(lines[i].type) == exdpy.LineType
        assert type(lines[i].timestamp) == int
        assert type(lines[i].channel) == str
        assert type(lines[i].message) == dict
    
def test_replay_stream():
    last_line: exdpy.TextLine = None
    count = 0
    for line in req.stream():
        assert type(line.exchange) == str
        assert type(line.type) == exdpy.LineType
        assert type(line.timestamp) == int
        assert type(line.channel) == str
        assert type(line.message) == dict
        if last_line is not None:
            assert last_line.timestamp <= line.timestamp
        last_line = line
        count += 1

    assert count != 0
    print('total of %d lines fetched', count)


