# exchangedataset-python

`exchangedataset-python` is a library for Python 3 to allow easy integration to Exchangedataset service.

## About Exchangedataset

Exchangedataset is the data streaming service of historical cryptocurrency market.

We aim to open the door of market data analyzation for everyone by providing reasonable, pay-by-transfer service.

## Requirements

- Python 3.8 or more
- Pipenv

## License

MIT License

This library is free to distribute and modify under the condition that you include a license notice.

## Install Library

To use this library, you can install this package by `pip3`:

```shell
pip3 install exchangedataset-python
```

This will install the latest and available version of this library.

As shown above, its package name in PyPi is [`exchangedataset-python`](https://pypi.org/project/exchangedataset-python/).

## Development

This information is for developper of this library.

Thank you for your contribution.

### Environment Setup

This project utilizes [Pipenv](https://pypi.org/project/pipenv/).

It is a package managing and virtual environment utility.

To fetch all dependencies (including development dependencies), run the command below:

```shell
pipenv install
```

This will install all dependencies needed to run, and compile `exchangedataset-python`.

### Test

Unit test files are under tests/ directory.

All tests can be conducted by running the command below:

```shell
pytest
```

### Deploy

The command below will package all python files under exdpy directory and upload it to PyPi.

```shell
python3 setup.py deploy
```
