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

import dateparser
from multiprocessing import Process
from pymongo import MongoClient
from twisted.internet import reactor

parser = argparse.ArgumentParser()
parser.add_argument('-e', '--exchange', type=str, default=None, help='Exchange for analysis (ex. binance / poloniex).')
parser.add_argument('-m', '--market', type=str, default=None, help='Market for analysis (ex. XLMBTC).')
parser.add_argument('-b', '--backtest', type=str, default=None, help='Length of time for historical trade data analysis (ex. 3 hours).')
parser.add_argument('-i', '--interval', type=int, default=10, help='Interval (seconds) between analysis runs (ex. 30). [Default: 10]')
parser.add_argument('--debug', action='store_true', default=False, help='Enable debug level output.')
args = parser.parse_args()

user_exchange = args.exchange
user_market = args.market
user_backtest_duration = args.backtest
analysis_interval = args.interval
debug_mode = args.debug

if user_exchange != None:
    user_exchange = user_exchange.lower()
if user_market != None:
    user_market = user_market.upper()

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

collections = {'data': config['mongodb']['collection_data'], 'analysis': config['mongodb']['collection_analysis']}


def process_message(msg, populate=False, exchange=None, market=None):
    process_message_success = True

    try:
        logger.debug('msg: ' + str(msg))

        trade_doc = {}

        update_required = False

        if populate == False:
            if 'M' in msg:
                exchange = 'binance'
                market = msg['s']
            else:
                exchange = 'poloniex'
        elif exchange == None or market == None:
            logger.error('Exchange and market names must be provided when populating database. Exiting.')
            sys.exit(1)

        if exchange == 'binance':
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
                else:
                    trade_doc['type'] = msg['e']
                trade_doc['exchange'] = exchange
                trade_doc['market'] = market
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

                logger_message = trade_doc['exchange'].capitalize() + '-' + trade_doc['market'] + ' - ' + trade_doc['side'].upper() + ' '
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


def populate_historical(exchange, market, start_time):
    if exchange == 'binance':
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
            process_result = process_message(trade, populate=True, exchange=exchange, market=market)

            if process_result == False:
                logger.info('Database population complete.')
                break
                #logger.info('Trade document already present in database.')
            else:
                count += 1
                completion_percentage = "{:.2f}".format((count / trade_count) * 100)
                logger.info('Processed ' + str(count) + ' of ~' + str(trade_count) + ' historical trades. [' + completion_percentage + '%]')

    elif exchange == 'poloniex':
        logger.warning('POLONIEX DATABASE POPULATION NOT YET IMPLEMENTED.')

    else:
        logger.error('Unrecognized exchange passed to populate_historical(). Exiting.')
        sys.exit(1)


#def analyze_data(market, feature, data, parameter, interval='1h', start=None):
def analyze_data(exchange, market, interval='1h', start=None):
    """
    exchange - Exchange to analyze (ex. binance)
    market - Market to analyze (ex. XLMBTC)
    interval - Duration to analyze (ex. 30s / 15m / 3h / 1d / 3w)
    start - UTC datetime object dictating start of analysis interval (Overrides interval argument)
    """

    analyze_return = {'success': True, 'result': {'current': {'volume': {'all': None, 'buy': None, 'sell': None},
                                                              'price': {'all': None, 'buy': None, 'sell': None},
                                                              'amount': {'all': None, 'buy': None, 'sell': None},
                                                              'count': {'all': None, 'buy': None, 'sell': None}},
                                                  'last': {'volume': {'all': None, 'buy': None, 'sell': None},
                                                           'price': {'all': None, 'buy': None, 'sell': None},
                                                           'amount': {'all': None, 'buy': None, 'sell': None},
                                                           'count': {'all': None, 'buy': None, 'sell': None}},
                                                  'difference': {'volume': {'all': {'absolute': None, 'percent': None},
                                                                            'buy': {'absolute': None, 'percent': None},
                                                                            'sell': {'absolute': None, 'percent': None}},
                                                                 'price': {'all': {'absolute': None, 'percent': None},
                                                                           'buy': {'absolute': None, 'percent': None},
                                                                           'sell': {'absolute': None, 'percent': None}},
                                                                 'amount': {'all': {'absolute': None, 'percent': None},
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
            match_pipeline_current = {'$match': {'exchange': exchange, 'market': market, 'trade_time': {'$gte': analysis_start}}}
            match_pipeline_last = {'$match': {'exchange': exchange, 'market': market, 'trade_time': {'$gte': analysis_start_last, '$lt': analysis_start}}}

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

            # Project Stage
            doc_structure = db[collections['data']].find({})[0]
            logger.debug('doc_structure: ' + str(doc_structure))

            project_pipeline = {'$project': {}}

            doc_fields = []
            for key in doc_structure:
                doc_fields.append(key)

            for field in doc_fields:
                project_pipeline['$project'][field] = 1

            project_pipeline['$project']['amount'] = {'$multiply': ['$price', '$quantity']}

            logger.debug('project_pipeline: ' + str(project_pipeline))

            pipeline_current.append(project_pipeline)
            pipeline_last.append(project_pipeline)

            # Group Stage
            group_pipeline = {'$group': {'_id': match,
                                         'volume': {'$sum': '$quantity'},
                                         'price': {'$avg': '$price'},
                                         'amount': {'$avg': '$amount'},
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
            amount_diff_absolute = round(result_current['amount'] - result_last['amount'], 8)
            amount_diff_percent = round(amount_diff_absolute / result_last['amount'], 4)
            count_diff_absolute = result_current['count'] - result_last['count']
            count_diff_percent = round(count_diff_absolute / result_last['count'], 4)

            # Add results to return dictionary
            analyze_return['result']['current']['volume'][match] = result_current['volume']
            analyze_return['result']['current']['price'][match] = round(result_current['price'], 8)
            analyze_return['result']['current']['amount'][match] = round(result_current['amount'], 8)
            analyze_return['result']['current']['count'][match] = result_current['count']
            analyze_return['result']['last']['volume'][match] = result_last['volume']
            analyze_return['result']['last']['price'][match] = round(result_last['price'], 8)
            analyze_return['result']['last']['amount'][match] = round(result_last['amount'], 8)
            analyze_return['result']['last']['count'][match] = result_last['count']
            analyze_return['result']['difference']['volume'][match]['absolute'] = vol_diff_absolute
            analyze_return['result']['difference']['volume'][match]['percent'] = vol_diff_percent
            analyze_return['result']['difference']['price'][match]['absolute'] = price_diff_absolute
            analyze_return['result']['difference']['price'][match]['percent'] = price_diff_percent
            analyze_return['result']['difference']['amount'][match]['absolute'] = amount_diff_absolute
            analyze_return['result']['difference']['amount'][match]['percent'] = amount_diff_percent
            analyze_return['result']['difference']['count'][match]['absolute'] = count_diff_absolute
            analyze_return['result']['difference']['count'][match]['percent'] = count_diff_percent

        # Calculate difference between requested interval start and first document trade time
        # Can use to warn user about data missing from requested calculation
        #first_doc_time = xyz

    except Exception as e:
        logger.exception(e)

        analyze_return['success'] = False

    finally:
        return analyze_return


def analysis_loop(backtest_duration):
    while (True):
        try:
            delay_start = time.time()
            while (time.time() - delay_start) < analysis_interval:
                time.sleep(1)

            logger.info('Analyzing trade data.')

            analysis_results = analyze_data(exchange=user_exchange, market=user_market, interval=backtest_duration)

            if analysis_results['success'] == True:
                analysis_document = analysis_results['result'].copy()
                #analysis_document['time'] = datetime.datetime.now().isoformat()
                analysis_document['module'] = 'flowmeter'
                analysis_document['exchange'] = user_exchange
                analysis_document['market'] = user_market

                pprint(analysis_document)

                #logger.info('Updating analysis database.')
                logger.info('Creating new analysis document.')

                #update_result = db[collections['analysis']].update_one({'_id': user_market}, {'$set': analysis_document}, upsert=True)
                #logger.debug('update_result.matched_count: ' + str(update_result.matched_count))
                #logger.debug('update_result.modified_count: ' + str(update_result.modified_count))
                inserted_id = db[collections['analysis']].insert_one(analysis_document).inserted_id
                logger.debug('inserted_id: ' + str(inserted_id))

            else:
                logger.error('Error while analyzing trade data.')

        except Exception as e:
            logger.exception(e)

        except KeyboardInterrupt:
            logger.info('Exit signal received in analysis process. Breaking loop.')
            break


if __name__ == '__main__':
    try:
        ## Get list of available Binance markets to verify user input ##
        binance_info = binance_client.get_exchange_info()

        binance_markets = []

        for product in binance_info['symbols']:
            binance_markets.append(product['baseAsset'] + product['quoteAsset'])

        trade_sockets = {}

        available_exchanges = ['binance', 'poloniex']

        ## Gather desired settings from user input ##
        if user_exchange == None:
            print('Available Exchanges:')
            print('1 - Binance')
            print('2 - Poloniex')
            exchange_input = int(input('Choose an exchange: '))

            if exchange_input == 1:
                user_exchange = 'binance'
            elif exchange_input == 2:
                user_exchange == 'poloniex'
            else:
                logger.error('Unrecognized exchange choice. Exiting.')
                sys.exit(1)

        elif user_exchange not in available_exchanges:
            logger.error('Unrecognized exchange name. Exiting.')
            sys.exit(1)

        if user_market == None:
            user_market = input('Choose a Binance market (ex. XLMBTC): ').upper()

            if user_market not in binance_markets:
                logger.error(user_market + ' is not a valid Binance market. Exiting.')
                sys.exit(1)
            else:
                logger.info('Selected Binance market ' + user_market + '.')

        if user_backtest_duration == None:
            user_backtest_duration = input('Input length of time for trade data backtesting/analysis (ex. 30 seconds/9 minutes/3 hours/2 days/1 week): ')

        backtest_duration_formatted = user_backtest_duration + ' ago UTC'
        logger.debug('backtest_duration_formatted: ' + backtest_duration_formatted)

        try:
            logger.debug('Testing user-provided historical data population input.')
            historical_trades = binance_client.aggregate_trade_iter(symbol=user_market, start_str=backtest_duration_formatted)
            logger.debug('Attempting count of trades in generator object.')
            trade_count = sum(1 for trade in historical_trades)
            #populate_duration = backtest_duration_formatted
            #logger.debug('populate_duration: ' + populate_duration)
        except Exception as e:
            logger.exception(e)
            logger.error('Invalid input for start of historical data population. Exiting.')
            sys.exit(1)

        if user_market == None or user_backtest_duration == None:
            logger.error('Failed to gather valid user input. Exiting.')
            sys.exit(1)

        backtest_duration = ''
        for char in user_backtest_duration:
            if char.isnumeric() == True:
                backtest_duration += char
            elif char == ' ':
                continue
            elif char.isalpha():
                backtest_duration += char
                break
        logger.debug('backtest_duration: ' + backtest_duration)

        ## Delete existing data for market from database ##
        logger.info('Deleting existing ' + user_market + ' data from database.')

        delete_result = db[collections['data']].delete_many({'market': user_market})
        logger.debug('delete_result.deleted_count: ' + str(delete_result.deleted_count))

        ## Initialize aggregated trade websocket for market ##
        logger.info('Initializing trade websocket for ' + user_market + '.')

        #trade_sockets[user_market] = binance_ws.start_trade_socket(user_market, process_message)
        trade_sockets[user_market] = binance_ws.start_aggtrade_socket(user_market, process_message)

        ## Start websocket for market and begin processing data ##
        logger.info('Starting websocket connection for ' + user_market + '.')

        binance_ws.start()

        ## Populate database with historical trade data for extended backtesting/analysis ##
        logger.info('Populating database with historical trade data.')

        backtest_delta = datetime.datetime.now(datetime.timezone.utc) - dateparser.parse(backtest_duration_formatted)
        logger.debug('backtest_delta: ' + str(backtest_delta))

        populate_delta = (backtest_delta * 2) + datetime.timedelta(hours=1) # Populate with 2x + 1 extra hour of data
        logger.debug('populate_delta: ' + str(populate_delta))

        #populate_start_dt = dateparser.parse(backtest_duration_formatted) - datetime.timedelta(hours=1)
        populate_start_dt = datetime.datetime.now() - populate_delta
        logger.debug('populate_start_dt: ' + str(populate_start_dt))

        populate_start = int(time.mktime(populate_start_dt.timetuple()) * 1000)
        logger.debug('populate_start:' + str(populate_start))

        arguments = tuple()
        keyword_arguments = {'exchange': user_exchange, 'market': user_market, 'start_time': populate_start}

        populate_proc = Process(target=populate_historical, args=arguments, kwargs=keyword_arguments)

        logger.debug('Starting populate database process.')
        populate_proc.start()
        logger.debug('Joining populate database process.')
        populate_proc.join()
        logger.debug('Populate database process complete.')

        logger.info('Database ready for analysis.')

        arguments = tuple()
        keyword_arguments = {'backtest_duration': backtest_duration}

        analysis_proc = Process(target=analysis_loop, args=arguments, kwargs=keyword_arguments)

        logger.info('Starting analysis.')

        logger.debug('Starting analysis process.')
        analysis_proc.start()
        logger.debug('Joining analysis process.')
        analysis_proc.join()

        logger.info('Exited analysis process.')

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
