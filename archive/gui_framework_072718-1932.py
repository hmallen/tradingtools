import logging
import os
import sys

import configparser
from pprint import pprint
import time
import tkinter as tk
import threading

from pymongo import MongoClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config.ini'

config = configparser.ConfigParser()
config.read(config_path)

mongo_uri = config['mongodb']['uri']

if mongo_uri == 'localhost':
    mongo_uri = None

db = MongoClient(mongo_uri)[config['mongodb']['db']]

collections = {'data': config['mongodb']['collection_data'], 'analysis': config['mongodb']['collection_analysis']}


class Display(threading.Thread):

    def __init__(self, master=None, update_interval=5):
        self.root = master

        self.update_interval = update_interval

        threading.Thread.__init__(self)

        #self.element_parameters = {}

        self.title_font = ('Helvetica', 16)
        self.text_font = ('Helvetica', 12)
        self.variable_font = ('Helvetica', 12)
        self.button_font = ('Helvetica', 10)

        self.trade_last_price = tk.DoubleVar()
        self.trade_last_quantity = tk.DoubleVar()
        self.trade_last_amount = tk.DoubleVar()
        self.trade_last_side = tk.StringVar()
        self.trade_last_side.set('N/A')

        self.create_widgets()

        self.start()

    def create_widgets(self):
        """
        - Title (Exchange/Market)
        - Subheading (Backtest interval)
        - Data display
        - Quit button
        """
        self.widgets = {'titles': {}, 'text': {}, 'variables': {}, 'buttons': {}}

        # Title Elements
        self.widgets['titles']['trade_title'] = tk.Label(self.root, text='STUFF & THINGS', font=self.title_font)

        # Trade Price
        self.widgets['text']['trade_last_price_label'] = tk.Label(self.root, text='Price:', font=self.text_font)
        self.widgets['text']['trade_last_price_label'].grid(row=0, column=0, sticky=tk.E)
        self.widgets['variables']['trade_last_price'] = tk.Label(self.root, textvariable=self.trade_last_price)

        self.background_transparent = self.widgets['variables']['trade_last_price'].cget('bg')   # Save OS-dependent "transparent" background color name
        logger.debug('self.background_transparent: ' + self.background_transparent)

        self.widgets['variables']['trade_last_price']['bg'] = 'red' # Set to red (update pending) after saving transparent background name
        self.widgets['variables']['trade_last_price'].grid(row=0, column=1, sticky=tk.W)

        # Trade Quantity
        self.widgets['text']['trade_last_quantity_label'] = tk.Label(self.root, text='Quantity:')
        self.widgets['text']['trade_last_quantity_label'].grid(row=1, column=0, sticky=tk.E)
        self.widgets['variables']['trade_last_quantity'] = tk.Label(self.root, textvariable=self.trade_last_quantity, bg='red')
        self.widgets['variables']['trade_last_quantity'].grid(row=1, column=1, sticky=tk.W)

        # Trade Amount
        self.widgets['text']['trade_last_amount_label'] = tk.Label(self.root, text='Amount:')
        self.widgets['text']['trade_last_amount_label'].grid(row=2, column=0, sticky=tk.E)
        self.widgets['variables']['trade_last_amount'] = tk.Label(self.root, textvariable=self.trade_last_amount, bg='red')
        self.widgets['variables']['trade_last_amount'].grid(row=2, column=1, sticky=tk.W)

        # Trade Side
        self.widgets['text']['trade_last_side_label'] = tk.Label(self.root, text='Side:')
        self.widgets['text']['trade_last_side_label'].grid(row=3, column=0, sticky=tk.E)
        self.widgets['variables']['trade_last_side'] = tk.Label(self.root, textvariable=self.trade_last_side, bg='red')
        self.widgets['variables']['trade_last_side'].grid(row=3, column=1, sticky=tk.W)

        # Variables to signal state of data
        self.trade_data_ready = False
        self.analysis_data_ready = False
        self.gui_data_ready = False

        # Data Ready Status Indicator
        self.widgets['text']['status_label'] = tk.Label(self.root, text='Update in progress...', bg='yellow')
        self.widgets['text']['status_label'].grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E)

        # Temporary Update Pending Message
        self.widgets['text']['update_pending_message'] = tk.Label(self.root, text='Updating GUI data, please wait...')
        self.widgets['text']['update_pending_message'].grid(column=0, columnspan=2, sticky=tk.W+tk.E)

        # Quit Button
        self.widgets['buttons']['quit_button'] = tk.Button(self.root, text='Quit', command=self.stop_display)
        self.widgets['buttons']['quit_button'].grid(column=0, columnspan=2, sticky=tk.S)

    def stop_display(self):
        self.display_active = False
        self.root.quit()
        #self.root.update()
        #self.root.destroy()

    def run(self):
        """
        for x in range(0, 5):
            if self.display_active == False:
                #self.stop_display()
                break
            self.trade_last_price.set(self.trade_last_price.get() + 1)
            time.sleep(1)
        else:
            logger.debug('Stopping display.')

            self.stop_display()
            self.root.update()
        """

        self.display_active = True

        while self.display_active == True:
            try:
                logger.debug('self.display_active: ' + str(self.display_active))

                delay_start = time.time()
                while (time.time() - delay_start) < self.update_interval:
                    if self.display_active == False: break
                    time.sleep(0.1)

                ## Get most recent trade info from database ##
                logger.debug('Retrieving most recent trade from database.')

                trade_pipeline = []

                # Sort stage to order with most recent trade first
                sort_pipeline = {'$sort': {'_id': -1}}
                trade_pipeline.append(sort_pipeline)

                # Limit stage to retrieve only most recent trade
                limit_pipeline = {'$limit': 1}
                trade_pipeline.append(limit_pipeline)

                # Run aggregation pipeline
                logger.debug('trade_pipeline: ' + str(trade_pipeline))

                aggregate_result = db.command('aggregate', collections['data'], cursor={}, pipeline=trade_pipeline)

                logger.debug('aggregate_result[\'ok\']: ' + str(aggregate_result['ok']))

                if aggregate_result['ok'] == 1:
                    trade_last = aggregate_result['cursor']['firstBatch'][0]

                    pprint(trade_last)

                    # Update GUI with recent trade info
                    update_trade_result = self.update_trade_display(trade_last)

                    if update_trade_result['success'] == True:
                        if self.trade_data_ready == False: self.trade_data_ready = True
                    else:
                        logger.error('Error while updating GUI with recent trade info.')

                else:
                    logger.error('Error returned from aggregation pipeline while retrieving most recent trade document.')

                ## Get most recent analysis info from database ##
                logger.debug('Retrieving most recent analysis from database.')

                analysis_pipeline = []

                # Sort stage to order with most recent analysis first
                sort_pipeline = {'$sort': {'time': -1}}
                analysis_pipeline.append(sort_pipeline)

                # Limit stage to retrieve only most recent analysis
                limit_pipeline = {'$limit': 1}
                analysis_pipeline.append(limit_pipeline)

                # Run aggregation pipeline
                logger.debug('analysis_pipeline: ' + str(analysis_pipeline))

                aggregate_result = db.command('aggregate', collections['analysis'], cursor={}, pipeline=analysis_pipeline)

                logger.debug('aggregate_result[\'ok\']: ' + str(aggregate_result['ok']))

                if aggregate_result['ok'] == 1:
                    analysis_last = aggregate_result['cursor']['firstBatch'][0]

                    pprint(analysis_last)

                    # Update GUI with recent analysis info
                    update_analysis_result = self.update_analysis_display(analysis_last)

                    if update_analysis_result['success'] == True:
                        if self.analysis_data_ready == False: self.analysis_data_ready = True
                    else:
                        logger.error('Error while updating GUI with recent analysis info.')

                if self.gui_data_ready == False:
                    if self.trade_data_ready == True and self.analysis_data_ready == True:
                        # Destroy update pending message widget
                        logger.debug('Destroying update pending message widget.')

                        self.widgets['text']['update_pending_message'].destroy()

                        self.widgets['text']['status_label']['text'] = 'Ready'
                        self.widgets['text']['status_label']['bg'] = 'green4'
                        self.widgets['text']['status_label'].update()

                        for var in self.widgets['variables']:
                            self.widgets['variables'][var].config(bg=self.background_transparent)

                        #self.root.update()

                        self.gui_data_ready = True

                        logger.info('GUI data fully updated and ready for use.')

            except Exception as e:
                logger.exception(e)

            except KeyboardInterrupt:
                logger.info('Exit signal received in main display loop.')

                logger.debug('Stopping display.')

                self.stop_display()
                self.root.update()

                break

        logger.debug('Exited main display loop.')

    def update_trade_display(self, data):
        update_return = {'success': True}

        try:
            # Update display values
            self.trade_last_price.set(round(data['price'], 8))
            self.trade_last_quantity.set(round(data['quantity'], 2))
            self.trade_last_amount.set(round(data['price'] * data['quantity'], 8))
            self.trade_last_side.set(data['side'].upper())

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        finally:
            return update_return

    def update_analysis_display(self, data):
        update_return = {'success': True}

        try:
            # UPDATE DISPLAY
            pass

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        finally:
            return update_return


if __name__ == '__main__':
    root = tk.Tk()
    app = Display(root)
    root.mainloop()
    root.destroy()
