import configparser
import logging
import os
import sys

from binance.client import Client as BinanceClient
from binance.websockets import BinanceSocketManager

from twisted.internet import reactor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config.ini'


def process_message(msg):
    """
    {
        "e": "trade",     # Event type
        "E": 123456789,   # Event time
        "s": "BNBBTC",    # Symbol
        "t": 12345,       # Trade ID
        "p": "0.001",     # Price
        "q": "100",       # Quantity
        "b": 88,          # Buyer order Id
        "a": 50,          # Seller order Id
        "T": 123456785,   # Trade time
        "m": true,        # Is the buyer the market maker?
        "M": true         # Ignore.
    }
    """
    pass


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(config_path)

    binance_api = config['binance']['api']
    binance_secret = config['binance']['secret']

    binance_client = BinanceClient(binance_api, binance_secret)

    binance_ws = BinanceSocketManager(binance_client)

    try:
        pass

    except Exception as e:
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        reactor.stop()
