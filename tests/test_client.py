import exdpy
import pytest

def test_without_apikey():
    with pytest.raises(TypeError):
        exdpy.Client()

def test_invalid_apikey():
    with pytest.raises(ValueError):
        exdpy.Client(apikey='th!si,ssoinvalid!')

def test_create_client():
    exdpy.Client(apikey='demo')
