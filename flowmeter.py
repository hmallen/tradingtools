import configparser
import logging
import os
import sys

from binance.client import Client as BinanceClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config.ini'


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(config_path)

    binance_api = config['binance']['api']
    binance_secret = config['binance']['secret']

    binance_client = BinanceClient(binance_api, binance_secret)
