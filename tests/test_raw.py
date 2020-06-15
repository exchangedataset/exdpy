import exdpy

def test_raw_download():
    cli = exdpy.Client(apikey='demo')
    req = cli.raw({
            'bitmex': ['orderBookL2']
        },
        '2020-01-01 00:00:00Z', 
        '2020-01-01 00:10:00Z'
    )
    lines = req.download()
    assert len(lines) != 0
    assert type(lines[0].exchange) == str
    assert type(lines[0].type) == exdpy.LineType
    assert type(lines[0].timestamp) == int
    assert type(lines[0].channel) == str
    assert type(lines[0].message) == str
    
def test_raw_stream():
    cli = exdpy.Client(apikey='demo')
    req = cli.raw({
            'bitmex': ['orderBookL2']
        },
        '2020-01-01 00:00:00Z', 
        '2020-01-01 01:00:00Z'
    )
    ita = req.stream()
    count = 0
    for line in ita:
        assert type(line.exchange) == str
        assert type(line.type) == exdpy.LineType
        assert type(line.timestamp) == int
        assert type(line.channel) == str
        assert type(line.message) == str
        count += 1

    assert count != 0
    print('total of %d lines fetched', count)
