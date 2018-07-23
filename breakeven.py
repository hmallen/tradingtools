import configparser
import logging
import os
import sys

from binance.client import Client as BinanceClient
from poloniex import Poloniex

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config.ini'

config = configparser.ConfigParser()
config.read(config_path)


if __name__ == '__main__':
    poloniex_api = config['poloniex']['api']
    poloniex_secret = config['poloniex']['secret']

    polo_client = Poloniex(poloniex_api, poloniex_secret)

    exchange = input('Choose Exchange (ex. poloniex): ').lower()

    if exchange not in available_exchanges:
        logger.error('Exchange not available. Exiting.')
        sys.exit(1)

    # GET MARKET LIST

    market = input('Choose Market (ex. STRBTC): ').upper()
