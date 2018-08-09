import configparser
import logging
import sys
import time

from binance.client import Client as BinanceClient
from binance.websockets import BinanceSocketManager

from twisted.internet import reactor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = '../config/config.ini'

def process_message(msg):
    print(msg)


if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        binance_api = config['binance']['api']
        binance_secret = config['binance']['secret']

        binance_client = BinanceClient(binance_api, binance_secret)
        binance_ws = BinanceSocketManager(binance_client)

        # Standard Approach
        sockets = {
            'candles': None,
            'ticker': None
        }

        logger.debug('Initializing candle socket.')
        sockets['candles'] = binance_ws.start_kline_socket('XLMBTC', process_message)

        logger.debug('Starting websocket.')
        binance_ws.start()

        logger.debug('10 second delay')
        time.sleep(10)

        logger.debug('Initializing symbol ticker socket.')
        sockets['ticker'] = binance_ws.start_symbol_ticker_socket('XLMBTC', process_message)

        logger.debug('10 second delay')
        time.sleep(10)

        logger.debug('Stopping candle socket.')
        binance_ws.stop_socket(sockets['candles'])

        logger.debug('sockets: ' + str(sockets))

        logger.debug('5 second delay')
        time.sleep(5)

        logger.debug('Initializing new candle socket.')
        sockets['candles'] = binance_ws.start_kline_socket('XLMBTC', process_message)

        # RESTART ATTEMPT FAILS ("THREAD CAN ONLY BE STARTED ONCE")
        #logger.debug('Restarting websocket.')
        #binance_ws.start()
        
        logger.debug('15 second delay')
        time.sleep(15)

        # Multiplex Approach
        #sockets_multiplex = []

        #

    except Exception as e:
        logger.exception(e)

    finally:
        if reactor.running:
            logger.info('Stopping Twisted Reactor.')
            reactor.stop()

        logger.info('Exiting.')
