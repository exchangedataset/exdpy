from exdpy import Client, LineType

cli = Client(apikey='demo')

def test_filter():
    lines = cli.http.filter('bitmex', ['orderBookL2'], '2020-01-01 00:00Z')
    assert len(lines) != 0
    assert type(lines[0].exchange) == str
    assert type(lines[0].type) == LineType
    assert type(lines[0].timestamp) == int
    assert type(lines[0].channel) == str
    assert type(lines[0].message) == str
    
def test_snapshot():
    lines = cli.http.snapshot('bitmex', ['orderBookL2'], '2020-01-01 00:01:24Z')
    assert len(lines) != 0
    assert type(lines[0].timestamp) == int
    assert type(lines[0].channel) == str
    assert type(lines[0].snapshot) == str
