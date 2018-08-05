import configparser
import datetime
import logging
import os
from pprint import pprint
import sys

import csv
import numpy as np
from pymongo import MongoClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config.ini'

#analysis_exchange = 'binance'
#analysis_market = 'XLMBTC'


def dump_data_csv(data, market):
    """
    analysis_data = {
        'x': [],
        'y': {
            'market_prices': {
                analysis_market: [],
                'BTCUSDT': []
            },
            'flow_differential': {}
        }
    }
    """

    dump_csv_return = {'success': True}

    try:
        #header = ['Time', 'BTCUSDT', market,
                  #'1 Minute', '5 Minute', '15 Minute',
                  #'30 Minute', '1 Hour', '2 Hour',
                  #'4 Hour', '6 Hour', '12 Hour', '1 Day']
        header = ['Time', 'BTCUSDT', market,
                  '5 Minute', '15 Minute', '30 Minute',
                  '1 Hour', '2 Hour', '4 Hour',
                  '6 Hour', '12 Hour', '1 Day']

        print(len(data['x']))
        print(len(data['y']['market_prices']['BTCUSDT']))
        print(len(data['y']['market_prices'][market]))
        #print(len(data['y']['flow_differential']['1m']))
        print(len(data['y']['flow_differential']['5m']))
        print(len(data['y']['flow_differential']['15m']))
        print(len(data['y']['flow_differential']['30m']))
        print(len(data['y']['flow_differential']['1h']))
        print(len(data['y']['flow_differential']['2h']))
        print(len(data['y']['flow_differential']['4h']))
        print(len(data['y']['flow_differential']['6h']))
        print(len(data['y']['flow_differential']['12h']))
        print(len(data['y']['flow_differential']['1d']))
        #sys.exit()

        with open('analysis.csv', 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)

            csv_writer.writerow(header)

            for x in range(0, len(data['x'])):
                logger.debug('Row #: ' + str(x))

                row = []

                row.append(data['x'][x])
                row.append(data['y']['market_prices']['BTCUSDT'][x] / 100)
                row.append(data['y']['market_prices'][market][x] * 1000000)
                #for interval in data['y']['flow_differential']:
                    #row.append(data['y']['flow_differential'][interval][x])
                #row.append(data['y']['flow_differential']['1m'][x])
                row.append(data['y']['flow_differential']['5m'][x])
                row.append(data['y']['flow_differential']['15m'][x])
                row.append(data['y']['flow_differential']['30m'][x])
                row.append(data['y']['flow_differential']['1h'][x])
                row.append(data['y']['flow_differential']['2h'][x])
                row.append(data['y']['flow_differential']['4h'][x])
                row.append(data['y']['flow_differential']['6h'][x])
                row.append(data['y']['flow_differential']['12h'][x])
                row.append(data['y']['flow_differential']['1d'][x])

                csv_writer.writerow(row)

    except Exception as e:
        logger.exception(e)

        dump_csv_return['success'] = False

    finally:
        return dump_csv_return


if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        mongo_uri = config['mongodb']['uri']

        if mongo_uri == 'localhost':
            mongo_uri = None

        db = MongoClient(mongo_uri)[config['mongodb']['db']]

        collections = {
            'data': config['mongodb']['collection_data'],
            'analysis': config['mongodb']['collection_analysis'],
            'historical': config['mongodb']['collection_historical'],
            'candles': config['mongodb']['collection_candles']
        }

        available_exchanges = ['binance']#, 'poloniex']

        available_exchanges.sort()

        ## Gather desired settings from user input ##
        print()
        print('Available Exchanges:')
        print()

        for exch in available_exchanges:
            print(str(available_exchanges.index(exch) + 1) + ' - ' + exch.capitalize())
        print()

        exchange_input = int(input('Choose an exchange: '))

        try:
            analysis_exchange = available_exchanges[exchange_input - 1]
        except:
            logger.error('Unrecognized exchange choice. Exiting.')
            sys.exit(1)

        logger.debug('analysis_exchange: ' + analysis_exchange)

        exchange_docs = db[collections['historical']].find({'exchange': analysis_exchange})

        available_markets = []

        for doc in exchange_docs:
            if doc['market'] not in available_markets:
                available_markets.append(doc['market'])

        logger.debug('available_markets: ' + str(available_markets))

        print()
        print('Available Markets:')
        print()

        for market in available_markets:
            print(str(available_markets.index(market) + 1) + ' - ' + market)
        print()

        market_input = int(input('Choose a market: '))

        try:
            analysis_market = available_markets[market_input - 1]
        except:
            logger.error('Unrecognized market choice. Exiting.')
            sys.exit(1)

        logger.debug('analysis_market: ' + analysis_market)

        print()
        print('Selected ' + analysis_exchange.capitalize() + '-' + analysis_market + '.')
        market_confirmation = input('Is this correct? [y/n]: ')

        if market_confirmation.lower() == 'y':
            logger.info('Selected ' + analysis_exchange.capitalize() + ' market ' + analysis_market + '.')
        elif market_confirmation.lower() == 'n':
            logger.info('Cancelled selection of ' + analysis_exchange.capitalize() + ' market ' + analysis_market + '. Exiting.')
            sys.exit()
        else:
            logger.error('Unrecognized selection for confirmation of market selection. Exiting.')
            sys.exit(1)

        analysis_docs = db[collections['historical']].find({'exchange': analysis_exchange, 'market': analysis_market}, sort=[('time', 1)])

        analysis_data = {
            'x': [],
            'y': {
                'market_prices': {
                    analysis_market: [],
                    'BTCUSDT': []
                },
                'flow_differential': {}
            }
        }

        analysis_dict_ready = False

        for doc in analysis_docs:
            if analysis_dict_ready == False:
                for interval in doc['values']:
                    analysis_data['y']['flow_differential'][interval] = []

                analysis_dict_ready = True

            analysis_data['x'].append(doc['time'])
            analysis_data['y']['market_prices'][analysis_market].append(doc['market_prices'][analysis_market])
            analysis_data['y']['market_prices']['BTCUSDT'].append(doc['market_prices']['BTCUSDT'])

            for interval in doc['values']:
                analysis_data['y']['flow_differential'][interval].append(doc['values'][interval])

        analysis_data['x'] = np.array(analysis_data['x'], dtype='f8')

        for category in analysis_data['y']:
            logger.debug('category: ' + category)

            for section in analysis_data['y'][category]:
                logger.debug('section: ' + section)

                analysis_data['y'][category][section] = np.array(analysis_data['y'][category][section], dtype='f8')

        dump_csv_result = dump_data_csv(analysis_data, analysis_market)

        if dump_csv_result['success'] == False:
            logger.error('Error while dumping data to csv file.')
        else:
            logger.info('Successfully dumped analysis data to csv file.')

        logger.info('Done.')

    except Exception as e:
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        logger.info('Exiting.')
