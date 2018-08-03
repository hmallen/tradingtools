import configparser
import logging
import os
from pprint import pprint
import time
import sys

#import numpy as np

from pymongo import MongoClient

from binance.client import Client as BinanceClient
from binance.websockets import BinanceSocketManager
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
    'candles': config['mongodb']['collection_candles']
}


def candle_handler(msg):
    candle = msg['k']

    candle_doc = {
        'exchange': 'binance',
        'market': candle['s'],
        'interval': candle['i'],
        'open_time': candle['t'],
        'open': candle['o'],
        'high': candle['h'],
        'low': candle['l'],
        'close': candle['c'],
        'volume': candle['v'],
        'close_time': candle['T'],
        'quote_currency_volume': candle['q'],
        'trade_count': candle['n'],
        'taker_buy_quote_volume': candle['Q'],
        'taker_buy_trade_volume': candle['V']
    }

    pprint(candle_doc)

    doc_match = {
        'exchange': 'binance',
        'market': candle['s'],
        'interval': candle['i'],
        'open_time': candle['t']
    }

    update_result = db[collections['candles']].update_one(doc_match, {'$set': candle_doc}, upsert=True)
    logger.debug('update_result.matched_count: ' + str(update_result.matched_count))
    logger.debug('update_result.modified_count: ' + str(update_result.modified_count))


if __name__ == '__main__':
    try:
        binance_api = config['binance']['api']
        binance_secret = config['binance']['secret']

        binance_client = BinanceClient(binance_api, binance_secret)
        binance_ws = BinanceSocketManager(binance_client)

        selected_market = 'XLMBTC'
        selected_interval = binance_client.KLINE_INTERVAL_1MINUTE

        logger.info('Deleting existing candle data from database.')

        doc_match = {
            'exchange': 'binance',
            'market': selected_market,
            'interval': '1m'
        }

        delete_result = db[collections['candles']].delete_many(doc_match)
        print(delete_result)

        time.sleep(5)

        sockets = {
            'binance': {}
        }

        sockets['binance'][selected_market] = binance_ws.start_kline_socket(symbol=selected_market, callback=candle_handler, interval=binance_client.KLINE_INTERVAL_1MINUTE)

        candles = binance_client.get_klines(symbol=selected_market, interval=selected_interval)

        # [open_time, open, high, low, close, volume, close_time, ..., ..., ..., ..., ...]

        for candle in candles:
            candle_doc = {
                'exchange': 'binance',
                'market': selected_market,
                'interval': '1m',
                'open_time': candle[0],
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
                'close_time': candle[6],
                'quote_currency_volume': candle[7],
                'trade_count': candle[8],
                'taker_buy_quote_volume': candle[9],
                'taker_buy_trade_volume': candle[10]
            }

            inserted_id = db[collections['candles']].insert_one(candle_doc)
            logger.debug('inserted_id: ' + str(inserted_id))

        binance_ws.start()

        while (True):
            time.sleep(0.1)

    except Exception as e:
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        if reactor.running:
            logger.info('Closing Binance socket manager.')
            binance_ws.close()

            logger.info('Stopping reactor.')
            reactor.stop()
        else:
            logger.info('No websocket connected or reactor running.')
