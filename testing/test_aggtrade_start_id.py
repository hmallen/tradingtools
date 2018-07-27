import configparser
import logging
import os
from pprint import pprint
import sys

from binance.client import Client as BinanceClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = '../config/config_testing.ini'


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(config_path)

    api = config['binance']['api']
    secret = config['binance']['secret']

    binance_client = BinanceClient(api, secret)

    historical_trades = binance_client.aggregate_trade_iter(symbol='XLMBTC', start_str='15 minutes ago UTC')

    trade_info = {}
    for trade in historical_trades:
        first_trade_id_agg = trade['a']
        first_trade_id_first = trade['f']
        first_trade_id_last = trade['l']
        break

    pprint(trade)

    ## WORKS ##
    print('Aggregate Trade ID Test:')
    try:
        historical_trades = binance_client.aggregate_trade_iter(symbol='XLMBTC', last_id=first_trade_id_agg)
        trade_list = list(historical_trades)
        trade_first = trade_list[0]
        print('First Trade:')
        pprint(trade_first)
        trade_last = trade_list[-1]
        print('Last Trade:')
        pprint(trade_last)
    except Exception as e:
        print('Aggregate trade id test failed.')
        print('Exception:', e)

    ## FAILS ##
    print('First Trade ID Test:')
    try:
        historical_trades = binance_client.aggregate_trade_iter(symbol='XLMBTC', last_id=first_trade_id_first)
        trade_list = list(historical_trades)
        trade_first = trade_list[0]
        print('First Trade:')
        pprint(trade_first)
        trade_last = trade_list[-1]
        print('Last Trade:')
        pprint(trade_last)
    except Exception as e:
        print('First trade id test failed.')
        print('Exception:', e)

    ## FAILS ##
    print('Last Trade ID Test:')
    try:
        historical_trades = binance_client.aggregate_trade_iter(symbol='XLMBTC', last_id=first_trade_id_last)
        trade_list = list(historical_trades)
        trade_first = trade_list[0]
        print('First Trade:')
        pprint(trade_first)
        trade_last = trade_list[-1]
        print('Last Trade:')
        pprint(trade_last)
    except Exception as e:
        print('Last trade id test failed.')
        print('Exception:', e)
