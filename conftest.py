"""Customize pytest configuration"""

from pytest import Config, Parser


def pytest_addoption(parser: Parser) -> None:  # noqa: D103
    parser.addoption(
        '--debug-sql', action='store_true', default=False, help='Print SQL queries on failure'
    )


def pytest_configure(config: Config) -> None:  # noqa: D103
    if config.getoption('--debug-sql'):
        from logging import DEBUG, getLogger

        getLogger('django.db.backends').setLevel(DEBUG)
