import argparse
import configparser
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
parser.add_argument('-d', '--debug', action='store_true', default=False, help='Enable debug level output.')
args = parser.parse_args()

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

    trade_count = sum(1 for trade in historical_trades)
    logger.debug('trade_count: ' + str(trade_count))

    # Get historical aggregated trade data again to refresh generator object (May make total count off by few trades)
    historical_trades = binance_client.aggregate_trade_iter(symbol=market, start_str=start_time)

    count = 0
    for trade in historical_trades:
        process_result = process_message(trade, populate=True, symbol=market)

        logger.info('Processed ' + str(count + 1) + ' of ~' + str(trade_count) + ' historical trades.')

        if process_result == False:
            logger.info('Database populated with ' + str(count) + ' historical trades.')
            break
        else:
            count += 1


def analyze_data(market, feature, interval='24h', start=None):
    """
    market - Market to analyze (ex. XLMBTC)
    feature - Analysis feature to calculate (ex. 'volume')
    interval - Duration to analyze (ex. 30s / 15m / 3h / 1d / 3w)
    start - Datetime object dictating start of analysis interval (Overrides interval argument)
    """

    try:
        if start != None:
            analysis_start = time.mktime(start.timetuple()) * 1000

        else:
            unix_time_ms = time.mktime(datetime.datetime.utcnow().timetuple()) * 1000
            logger.debug('unix_time_ms: ' + str(unix_time_ms))

            numerical = ''
            identifier = ''
            for char in interval:
                if char.isnumeric():
                    numerical.append(char)
                else:
                    identifier = char
                    break
            logger.debug('numerical: ' + numerical)
            logger.debug('identifier: ' + identifier)

            num_input = int(numerical)

            if identifier == 's':
                analysis_start = unix_time_ms - (num_input * 1000)
            elif identifier == 'm':
                analysis_start = unix_time_ms - (num_input * 60000)
            elif identifier == 'h':
                analysis_start = unix_time_ms - (num_input * 3600000)
            elif identifier == 'd':
                analysis_start = unix_time_ms - (num_input * 86,400,000)
            elif identifier == 'w':
                analysis_start = unix_time_ms - (num_input * 604800000)
            else:
                logger.error('Unrecognized interval identifier. Exiting.')
                sys.exit(1)

        # Create aggregation pipeline
        """
        pipeline = [{
            '$match': {'symbol': market}, {'trade_time': {'$gte': analysis_start}}
            }]
        """

        #first_doc_time = xyz

        if feature == 'XYZ':
            pass

    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    try:
        ## Get list of available Binance markets to verify user input ##
        binance_info = binance_client.get_exchange_info()

        binance_markets = []

        for product in binance_info['symbols']:
            binance_markets.append(product['baseAsset'] + product['quoteAsset'])

        trade_sockets = {}

        ## Gather desired settings from user input ##
        user_market = None
        populate_db = None
        populate_duration = None

        user_market = input('Choose a Binance market (ex. XLMBTC): ').upper()

        if user_market not in binance_markets:
            logger.error(user_market + ' is not a valid Binance market. Exiting.')
            sys.exit(1)
        else:
            logger.info('Selected Binance market ' + user_market + '.')

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
            user_populate_duration = input('Input desired start of historical data population (ex. 3 hours ago / 2 days ago / 1 week ago): ')

            test_duration = user_populate_duration + ' UTC'
            logger.debug('test_duration: ' + test_duration)

            try:
                historical_trades = binance_client.aggregate_trade_iter(symbol=user_market, start_str=test_duration)
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

        logger.debug('Entering main loop.')

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

        logger.info('Exiting.')
