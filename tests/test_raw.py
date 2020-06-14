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
    assert type(lines[0].type) == exdpy.LineType
    assert type(lines[0].timestamp) == int
    assert type(lines[0].channel) == str
    assert type(lines[0].message) == str
    