import argparse
import configparser
import datetime
import logging
import os
import sys
import time

from pprint import pprint

from binance.client import Client as BinanceClient
from binance.websockets import BinanceSocketManager

from multiprocessing import Process
from pymongo import MongoClient
from twisted.internet import reactor

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--interval', type=int, default=10, help='Interval (seconds) between each analysis run.')
parser.add_argument('-m', '--market', type=str, default=None, help='Market for analysis (ex. XLMBTC).')
parser.add_argument('-p', '--populate', action='store_true', default=None, help='Populate database with historical trade data.')
parser.add_argument('-d', '--duration', type=str, default=None, help='Amount of historical data for database population (ex. 3 days).')
parser.add_argument('--debug', action='store_true', default=False, help='Enable debug level output.')
args = parser.parse_args()

analysis_interval = args.interval
user_market = args.market
populate_db = args.populate
user_populate_duration = args.duration
debug_mode = args.debug

logging.basicConfig()
logger = logging.getLogger(__name__)

if debug_mode == True:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

config_path = 'config/config.ini'

config = configparser.ConfigParser()
config.read(config_path)

binance_api = config['binance']['api']
binance_secret = config['binance']['secret']

binance_client = BinanceClient(binance_api, binance_secret)
binance_ws = BinanceSocketManager(binance_client)

db = MongoClient(config['mongodb']['uri'])[config['mongodb']['db']]

collections = {'data': 'testing', 'analysis': 'analysis'}


def process_message(msg, populate=False, symbol=None):
    process_message_success = True

    try:
        logger.debug('msg: ' + str(msg))

        trade_doc = {}

        update_required = False

        if populate == True or msg['e'] == 'aggTrade':
            """
            {
                "e": "aggTrade",        # event type
                "E": 1499405254326,     # event time
                "s": "ETHBTC",          # symbol
                "a": 70232,             # aggregated tradeid
                "p": "0.10281118",      # price
                "q": "8.15632997",      # quantity
                "f": 77489,             # first breakdown trade id
                "l": 77489,             # last breakdown trade id
                "T": 1499405254324,     # trade time
                "m": false,             # whether buyer is a maker
                "M": true               # can be ignored
            }
            """

            trade_doc['_id'] = int(msg['a'])        # Aggregate Trade ID
            if populate == True:
                trade_doc['type'] = 'populate'
                trade_doc['symbol'] = symbol
            else:
                trade_doc['type'] = msg['e']
                trade_doc['symbol'] = msg['s']
            trade_doc['price'] = float(msg['p'])
            trade_doc['quantity'] = float(msg['q'])
            trade_doc['trade_time'] = int(msg['T'])
            if msg['m'] == True:
                trade_doc['side'] = 'sell'
            else:
                trade_doc['side'] = 'buy'
            #trade_doc['event_time'] = int(msg['E'])
            #trade_doc['trade_id_first'] = int(msg['f'])
            #trade_doc['trade_id_last'] = int(msg['l'])

            update_required = True

        elif msg['e'] == 'trade':
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

            trade_doc['_id'] = int(msg['t'])    # Trade ID
            trade_doc['type'] = msg['e']
            trade_doc['symbol'] = msg['s']
            trade_doc['price'] = float(msg['p'])
            trade_doc['quantity'] = float(msg['q'])
            trade_doc['trade_time'] = int(msg['T'])
            if msg['m'] == True:
                trade_doc['side'] = 'sell'
            else:
                trade_doc['side'] = 'buy'
            #trade_doc['event_time'] = int(msg['E'])
            #trade_doc['buyer_order_id'] = int(msg['b'])
            #trade_doc['seller_order_id'] = int(msg['a'])

            update_required = True

        elif msg['e'] == 'error':
            logger.error('Error message received from websocket.')
            logger.error('Error: ' + msg['m'])

            process_message_success = False

            logger.warning('Restarting websocket connection.')

            # RESTART WEBSOCKET CONNECTION HERE

        else:
            logger.warning('Unknown event type: ' + msg['e'])

            process_message_success = False

        if update_required == True:
            try:
                inserted_id = db[collections['data']].insert_one(trade_doc).inserted_id

                logger_message = trade_doc['symbol'] + ' - ' + trade_doc['side'].upper() + ' '
                if trade_doc['side'] == 'buy': logger_message += ' '
                logger_message += '- ' + str(trade_doc['quantity']) + ' @ ' + str(trade_doc['price'])
                if trade_doc['type'] == 'populate': logger_message += ' [' + trade_doc['type'].upper() + ']'

                if populate == False:
                    logger.info(logger_message)
                else:
                    logger.debug(logger_message)

            except:
                logger.warning('Exception while creating trade document. Can be safely ignored if raised while populating database.')

                process_message_success = False

    except Exception as e:
        logger.exception(e)

        process_message_success = False

    finally:
        return process_message_success


def populate_historical(market, start_time):
    binance_api = config['binance']['api']
    binance_secret = config['binance']['secret']

    binance_client = BinanceClient(binance_api, binance_secret)

    # Get historical aggregated trade data as generator object and count number of historical trades
    historical_trades = binance_client.aggregate_trade_iter(symbol=market, start_str=start_time)

    logger.info('Counting historical trades for database population.')

    trade_count = sum(1 for trade in historical_trades)
    logger.debug('trade_count: ' + str(trade_count))

    # Get historical aggregated trade data again to refresh generator object (May make total count off by few trades)
    historical_trades = binance_client.aggregate_trade_iter(symbol=market, start_str=start_time)

    count = 0
    for trade in historical_trades:
        process_result = process_message(trade, populate=True, symbol=market)

        if process_result == False:
            logger.info('Database population complete.')
            break
        else:
            count += 1
            logger.info('Processed ' + str(count) + ' of ~' + str(trade_count) + ' historical trades.')


#def analyze_data(market, feature, data, parameter, interval='1h', start=None):
def analyze_data(market, interval='1h', start=None):
    """
    market - Market to analyze (ex. XLMBTC)
    interval - Duration to analyze (ex. 30s / 15m / 3h / 1d / 3w)
    start - UTC datetime object dictating start of analysis interval (Overrides interval argument)
    """

    analyze_return = {'success': True, 'result': {'current': {'volume': {'all': None, 'buy': None, 'sell': None},
                                                              'price': {'all': None, 'buy': None, 'sell': None},
                                                              'count': {'all': None, 'buy': None, 'sell': None}},
                                                  'last': {'volume': {'all': None, 'buy': None, 'sell': None},
                                                           'price': {'all': None, 'buy': None, 'sell': None},
                                                           'count': {'all': None, 'buy': None, 'sell': None}},
                                                  'difference': {'volume': {'all': {'absolute': None, 'percent': None},
                                                                            'buy': {'absolute': None, 'percent': None},
                                                                            'sell': {'absolute': None, 'percent': None}},
                                                                 'price': {'all': {'absolute': None, 'percent': None},
                                                                           'buy': {'absolute': None, 'percent': None},
                                                                           'sell': {'absolute': None, 'percent': None}},
                                                                 'count': {'all': {'absolute': None, 'percent': None},
                                                                           'buy': {'absolute': None, 'percent': None},
                                                                           'sell': {'absolute': None, 'percent': None}}}}}

    try:
        if start != None:
            analysis_start = time.mktime(start.timetuple()) * 1000

        else:
            #unix_time_ms = int(time.mktime(datetime.datetime.utcnow().timetuple()) * 1000)
            unix_time_ms = int(time.mktime(datetime.datetime.now().timetuple()) * 1000)
            logger.debug('unix_time_ms: ' + str(unix_time_ms))

            numerical = ''
            identifier = ''
            for char in interval:
                if char.isnumeric():
                    numerical += char
                else:
                    identifier = char
                    break
            logger.debug('numerical: ' + numerical)
            logger.debug('identifier: ' + identifier)

            num_input = int(numerical)

            if identifier == 's':
                analysis_delta = num_input * 1000
            elif identifier == 'm':
                analysis_delta = num_input * 60000
            elif identifier == 'h':
                analysis_delta = num_input * 3600000
            elif identifier == 'd':
                analysis_delta = num_input * 86400000
            elif identifier == 'w':
                analysis_delta = num_input * 604800000
            else:
                logger.error('Unrecognized interval identifier. Exiting.')
                sys.exit(1)

            logger.debug('analysis_delta: ' + str(analysis_delta))

            analysis_start = unix_time_ms - analysis_delta
            logger.debug('analysis_start: ' + str(analysis_start))
            analysis_start_last = analysis_start - analysis_delta
            logger.debug('analysis_start_last: ' + str(analysis_start_last))

        match_inputs = ['all', 'buy', 'sell']

        for match in match_inputs:
            ## Create Aggregation Pipeline ##
            pipeline_current = []
            pipeline_last = []

            # Match Stage
            match_pipeline_current = {'$match': {'symbol': market, 'trade_time': {'$gte': analysis_start}}}
            match_pipeline_last = {'$match': {'symbol': market, 'trade_time': {'$gte': analysis_start_last, '$lt': analysis_start}}}

            if match == 'all':
                pass
            elif match == 'buy':
                match_pipeline_current['$match']['side'] = 'buy'
                match_pipeline_last['$match']['side'] = 'buy'
            elif match == 'sell':
                match_pipeline_current['$match']['side'] = 'sell'
                match_pipeline_last['$match']['side'] = 'sell'

            logger.debug('match_pipeline_current: ' + str(match_pipeline_current))
            logger.debug('match_pipeline_last: ' + str(match_pipeline_last))

            pipeline_current.append(match_pipeline_current)
            pipeline_last.append(match_pipeline_last)

            # Sort Stage
            sort_pipeline = {'$sort': {'_id': 1}}

            logger.debug('sort_pipeline: ' + str(sort_pipeline))

            pipeline_current.append(sort_pipeline)
            pipeline_last.append(sort_pipeline)

            # Group Stage
            group_pipeline = {'$group': {'_id': match,
                                         'volume': {'$sum': '$quantity'},
                                         'price': {'$avg': '$price'},
                                         'count': {'$sum': 1}}}

            logger.debug('group_pipeline: ' + str(group_pipeline))

            pipeline_current.append(group_pipeline)
            pipeline_last.append(group_pipeline)

            ## Run Aggregation Pipelines ##
            #aggregate_result_current = db.command('aggregate', collections['data'], cursor={}, pipeline=pipeline_current)
            aggregate_result_current = db[collections['data']].aggregate(pipeline_current)
            #aggregate_result_last = db.command('aggregate', collections['data'], cursor={}, pipeline=pipeline_last)
            aggregate_result_last = db[collections['data']].aggregate(pipeline_last)

            result_current = list(aggregate_result_current)[0]
            result_last = list(aggregate_result_last)[0]

            # Calculate differences to add to return dictionary
            vol_diff_absolute = result_current['volume'] - result_last['volume']
            vol_diff_percent = round(vol_diff_absolute / result_last['volume'], 4)
            price_diff_absolute = round(result_current['price'] - result_last['price'], 8)
            price_diff_percent = round(price_diff_absolute / result_last['price'], 4)
            count_diff_absolute = result_current['count'] - result_last['count']
            count_diff_percent = round(count_diff_absolute / result_last['count'], 4)

            # Add results to return dictionary
            analyze_return['result']['current']['volume'][result_current['_id']] = result_current['volume']
            analyze_return['result']['current']['price'][result_current['_id']] = round(result_current['price'], 8)
            analyze_return['result']['current']['count'][result_current['_id']] = result_current['count']
            analyze_return['result']['last']['volume'][result_last['_id']] = result_last['volume']
            analyze_return['result']['last']['price'][result_last['_id']] = round(result_last['price'], 8)
            analyze_return['result']['last']['count'][result_last['_id']] = result_last['count']
            analyze_return['result']['difference']['volume'][result_current['_id']]['absolute'] = vol_diff_absolute
            analyze_return['result']['difference']['volume'][result_current['_id']]['percent'] = vol_diff_percent
            analyze_return['result']['difference']['price'][result_current['_id']]['absolute'] = price_diff_absolute
            analyze_return['result']['difference']['price'][result_current['_id']]['percent'] = price_diff_percent
            analyze_return['result']['difference']['count'][result_current['_id']]['absolute'] = count_diff_absolute
            analyze_return['result']['difference']['count'][result_current['_id']]['percent'] = count_diff_percent

        # Calculate difference between requested interval start and first document trade time
        # Can use to warn user about data missing from requested calculation
        #first_doc_time = xyz

    except Exception as e:
        logger.exception(e)

        analyze_return['success'] = False

    finally:
        return analyze_return


if __name__ == '__main__':
    try:
        ## Get list of available Binance markets to verify user input ##
        binance_info = binance_client.get_exchange_info()

        binance_markets = []

        for product in binance_info['symbols']:
            binance_markets.append(product['baseAsset'] + product['quoteAsset'])

        trade_sockets = {}

        ## Gather desired settings from user input ##
        #user_market = None
        #populate_db = None
        #populate_duration = None

        if user_market == None:
            user_market = input('Choose a Binance market (ex. XLMBTC): ').upper()

            if user_market not in binance_markets:
                logger.error(user_market + ' is not a valid Binance market. Exiting.')
                sys.exit(1)
            else:
                logger.info('Selected Binance market ' + user_market + '.')

        if populate_db == None:
            user_populate_db = input('Populate database with historical trades? [y/n]: ').upper()

            if user_populate_db != 'Y' and user_populate_db != 'N':
                logger.error('Invalid selection. Exiting.')
                sys.exit(1)
            else:
                if user_populate_db == 'Y':
                    populate_db = True
                    pop_msg = 'Populating '
                else:
                    populate_db = False
                    pop_msg = 'Not populating '
                pop_msg += 'database with historical trade data.'

                logger.info(pop_msg)

        if populate_db == True:
            if user_populate_duration == None:
                user_populate_duration = input('Input desired amount of historical data for database population (ex. 30 seconds/9 minutes/3 hours/2 days/1 week): ')

            test_duration = user_populate_duration + ' ago UTC'
            logger.debug('test_duration: ' + test_duration)

            try:
                logger.debug('Testing user-provided historical data population input.')
                historical_trades = binance_client.aggregate_trade_iter(symbol=user_market, start_str=test_duration)
                logger.debug('Attempting count of trades in generator object.')
                trade_count = sum(1 for trade in historical_trades)
                populate_duration = test_duration
                logger.debug('populate_duration: ' + populate_duration)
            except:
                logger.error('Invalid input for start of historical data population. Exiting.')
                sys.exit(1)

        if user_market == None or populate_db == None:
            logger.error('Failed to gather valid user input. Exiting.')
            sys.exit(1)
        elif populate_db != None and populate_duration == None:
            logger.error('Failed to gather historical trade data population duration. Exiting.')
            sys.exit(1)

        ## Delete existing data for market from database ##
        logger.info('Deleting existing ' + user_market + ' data from database.')

        delete_result = db[collections['data']].delete_many({'symbol': user_market})
        logger.debug('delete_result.deleted_count: ' + str(delete_result.deleted_count))

        ## Initialize aggregated trade websocket for market ##
        logger.info('Initializing trade websocket for ' + user_market + '.')

        #trade_sockets[user_market] = binance_ws.start_trade_socket(user_market, process_message)
        trade_sockets[user_market] = binance_ws.start_aggtrade_socket(user_market, process_message)

        ## Start websocket for market and begin processing data ##
        logger.info('Starting websocket connection for ' + user_market + '.')

        binance_ws.start()

        if populate_db == True:
            ## Populate database with historical trade data for extended backtesting/analysis ##
            logger.info('Populating database with historical trade data.')

            arguments = tuple()
            keyword_arguments = {'market': user_market, 'start_time': populate_duration}

            populate_proc = Process(target=populate_historical, args=arguments, kwargs=keyword_arguments)

            logger.debug('Starting populate database process.')
            populate_proc.start()
            logger.debug('Joining populate database process.')
            populate_proc.join()
            logger.debug('Populate database process complete.')

        logger.info('Database ready for analysis.')

        while (True):
            delay_start = time.time()
            while (time.time() - delay_start) < analysis_interval:
                time.sleep(1)

            logger.info('Running analysis.')

            analysis_results = analyze_data(market=user_market, interval='12h')

            if analysis_results['success'] == True:
                pprint(analysis_results['result'])
            else:
                logger.error('Error while analyzing trade data.')

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

        logger.info('Exiting.')
