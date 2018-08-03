import configparser
import logging
import os
from pprint import pprint
import time
import sys

from pymongo import MongoClient
from multiprocessing import Process

from binance.client import Client as BinanceClient
#from binance.websockets import BinanceSocketManager
from binance.depthcache import DepthCacheManager
from twisted.internet import reactor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = '../config/config.ini'

config = configparser.ConfigParser()
config.read(config_path)

mongo_uri = config['mongodb']['uri']

if mongo_uri == 'localhost':
    mongo_uri = None

db = MongoClient(mongo_uri)[config['mongodb']['db']]

collections = {
    'data': config['mongodb']['collection_data'],
    'analysis': config['mongodb']['collection_analysis'],
    'candles': config['mongodb']['collection_candles']#,
    #'orderbook': config['mongodb']['collection_orderbook']
}


def orderbook_handler(depth_cache):
    if depth_cache != None:
        asks = depth_cache.get_asks()[:5]
        bids = depth_cache.get_bids()[:5]

        ask_book = ''
        for x in range((len(asks) - 1), -1, -1):
            ask_book += "{:<.8f} {:>.2f}".format(asks[x][0], asks[x][1]) + '\n'
        ask_book = ask_book.rstrip('\n')

        bid_book = ''
        for x in range(0, len(bids)):
            bid_book += "{:<.8f} {:>.2f}".format(bids[x][0], bids[x][1]) + '\n'
        bid_book = bid_book.rstrip('\n')

        print()
        print('Asks:')
        print(ask_book)
        print('----------------')
        print('Bids:')
        print(bid_book)
        print()

    else:
        # depth cache had an error and needs to be restarted
        logger.error('Error while retrieving market depth cache.')


if __name__ == '__main__':
    try:
        binance_api = config['binance']['api']
        binance_secret = config['binance']['secret']

        binance_client = BinanceClient(binance_api, binance_secret)
        #binance_ws = BinanceSocketManager(binance_client)

        selected_market = 'XLMBTC'

        binance_dcm = DepthCacheManager(binance_client, symbol=selected_market, callback=orderbook_handler, refresh_interval=300)

        start_time = time.time()
        while (time.time() - start_time) < 15:
            time.sleep(0.1)

    except Exception as e:
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        if reactor.running:
            logger.info('Closing Binance socket manager.')
            binance_dcm.close()

            logger.info('Stopping reactor.')
            reactor.stop()
        else:
            logger.info('No websocket connected or reactor running.')
