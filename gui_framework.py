import logging
import os
import sys

import configparser
import datetime
from pprint import pprint
import time
import tkinter as tk
import threading

from pymongo import MongoClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_path = 'config/config_testing.ini'

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

        self.images = {'trade': {}, 'analysis': {}}
        self.images['trade']['arrow_buy'] = tk.PhotoImage(file='resources/gui/arrow_buy_small.gif')
        self.images['trade']['arrow_sell'] = tk.PhotoImage(file='resources/gui/arrow_sell_small.gif')

        self.fonts = {'trade': {}, 'analysis': {}}
        self.fonts['trade']['titles'] = ('Helvetica', 12)
        self.fonts['trade']['text'] = ('Helvetica', 10)
        self.fonts['trade']['variables'] = ('Helvetica', 10)
        self.fonts['trade']['buttons'] = ('Helvetica', 10)

        self.colors = {'trade': {'bg': {}, 'text': {}}, 'analysis': {'bg': {}, 'text': {}}, 'transparent': None}
        self.colors['trade']['bg']['ready'] = 'green4'
        self.colors['trade']['bg']['notready'] = 'yellow'
        self.colors['trade']['bg']['warning'] = 'red'
        self.colors['trade']['bg']['buy'] = 'green2'
        self.colors['trade']['bg']['sell'] = 'red2'

        # Create dynamically updating GUI variables
        self.variables = {'trade': {}, 'analysis': {}}
        self.variables['trade']['price'] = tk.StringVar()
        self.variables['trade']['quantity'] = tk.StringVar()
        self.variables['trade']['amount'] = tk.StringVar()
        self.variables['trade']['status'] = tk.StringVar()
        # Give variables initial values
        self.variables['trade']['price'].set("{:.8f}".format(0))
        self.variables['trade']['quantity'].set("{:.2f}".format(0))
        self.variables['trade']['amount'].set("{:.4f}".format(0))
        self.variables['trade']['status'].set('Updating')

        self.update_last = {'trade': None, 'analysis': None}

        self.create_widgets()

        self.start()

    def create_widgets(self):
        """
        - Title (Exchange/Market)
        - Subheading (Backtest interval)
        - Data display
        - Quit button
        """

        ## Create Frames ##
        self.trade_frame = tk.Frame(self.root)
        #self.analysis_frame = tk.Frame(self.root)
        self.buttons_frame = tk.Frame(self.root)

        self.trade_frame.grid(row=0)
        #self.analysis_frame.grid(row=0, column=1)
        self.buttons_frame.grid(row=1)

        ## Create Widgets ##
        # Create dictionary for widget storage
        self.widgets = {'trade': {'titles': {}, 'text': {}, 'variables': {}, 'buttons': {}},
                        'analysis': {'titles': {}, 'text': {}, 'variables': {}, 'buttons': {}}}

        # Trade Title
        self.widgets['trade']['titles']['main'] = tk.Label(self.trade_frame, text='Last Trade')

        self.colors['transparent'] = self.widgets['trade']['titles']['main'].cget('bg')   # Save OS-dependent "transparent" background color name
        logger.debug('self.colors[\'transparent\']: ' + self.colors['transparent'])

        # Text Labels
        self.widgets['trade']['text']['price'] = tk.Label(self.trade_frame, text='Price:')
        self.widgets['trade']['text']['quantity'] = tk.Label(self.trade_frame, text='Quantity:')
        self.widgets['trade']['text']['amount'] = tk.Label(self.trade_frame, text='Amount:')

        # Variables
        self.widgets['trade']['variables']['price'] = tk.Label(self.trade_frame, textvariable=self.variables['trade']['price'], compound=tk.RIGHT)
        self.widgets['trade']['variables']['quantity'] = tk.Label(self.trade_frame, textvariable=self.variables['trade']['quantity'])
        self.widgets['trade']['variables']['amount'] = tk.Label(self.trade_frame, textvariable=self.variables['trade']['amount'])

        # Status Indicator
        self.widgets['trade']['variables']['status'] = tk.Label(self.trade_frame, textvariable=self.variables['trade']['status'])

        # Buttons
        self.widgets['trade']['buttons']['quit'] = tk.Button(self.buttons_frame, text='Quit', command=self.stop_display)

        # Format Text
        for category in self.widgets['trade']:
            logger.debug('category: ' + category)

            for element in self.widgets['trade'][category]:
                logger.debug('element: ' + element)

                selected_font = self.fonts['trade'][category]
                logger.debug('selected_font: ' + str(selected_font))

                self.widgets['trade'][category][element].config(font=selected_font)

                if category == 'variables':
                    self.widgets['trade'][category][element].config(bg=self.colors['trade']['bg']['notready'])

        ## Create Grid Layout ##
        self.widgets['trade']['titles']['main'].grid(row=0, columnspan=2)

        self.widgets['trade']['text']['price'].grid(row=1, column=0, sticky=tk.E); self.widgets['trade']['variables']['price'].grid(row=1, column=1, sticky=tk.W)
        self.widgets['trade']['text']['quantity'].grid(row=2, column=0, sticky=tk.E); self.widgets['trade']['variables']['quantity'].grid(row=2, column=1, sticky=tk.W)
        self.widgets['trade']['text']['amount'].grid(row=3, column=0, sticky=tk.E); self.widgets['trade']['variables']['amount'].grid(row=3, column=1, sticky=tk.W)

        self.widgets['trade']['variables']['status'].grid(row=4, columnspan=2, sticky=tk.E+tk.W)

        self.widgets['trade']['buttons']['quit'].grid(row=5, columnspan=2)

        # Variables to signal state of data
        self.trade_data_ready = False
        self.analysis_data_ready = False
        self.gui_data_ready = False

    def stop_display(self):
        self.display_active = False
        self.root.quit()
        #self.root.update()
        #self.root.destroy()

    def run(self):
        self.display_active = True

        while self.display_active == True:
            try:
                logger.debug('self.display_active: ' + str(self.display_active))

                delay_start = time.time()
                while (time.time() - delay_start) < self.update_interval:
                    if self.display_active == False: break

                    """
                    status_message = 'Last Update: '
                    if self.update_last['trade'] == None:
                        status_message += 'N/A'
                    else:
                        status_message += "{:.0f}".format((datetime.datetime.now() - self.update_last['trade']).total_seconds()) + ' sec ago'
                    logger.debug('status_message: ' + status_message)

                    self.variables['trade']['status'].set(status_message)
                    """

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
                        self.root.quit()

                else:
                    logger.error('Error returned from aggregation pipeline while retrieving most recent trade document.')
                    time.sleep(10)

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
                        time.sleep(10)

                if self.gui_data_ready == False:
                    if self.trade_data_ready == True and self.analysis_data_ready == True:
                        # Destroy update pending message widget
                        logger.debug('Destroying update pending message widget.')

                        #self.widgets['trade']['text']['update_pending'].destroy()#.grid_forget()

                        self.variables['trade']['status'].set('Ready')

                        for var in self.widgets['trade']['variables']:
                            #if var != 'side':
                            if var == 'status':
                                selected_color = self.colors['trade']['bg']['ready']
                            else:
                                selected_color = self.colors['transparent']
                            logger.debug('selected_color: ' + selected_color)

                            self.widgets['trade']['variables'][var].config(bg=selected_color)
                            #self.widgets['trade']['variables'][var].update()

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
            self.variables['trade']['price'].set("{:.8f}".format(data['price']) + ' ')
            self.variables['trade']['quantity'].set("{:.2f}".format(data['quantity']))
            self.variables['trade']['amount'].set("{:.4f}".format(data['price'] * data['quantity']))
            if data['side'] == 'buy':
                self.widgets['trade']['variables']['price'].config(image=self.images['trade']['arrow_buy'])
            else:
                self.widgets['trade']['variables']['price'].config(image=self.images['trade']['arrow_sell'])

            self.update_last['trade'] = datetime.datetime.now()

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        except KeyboardInterrupt:
            logger.info('Exit signal received while updating trade display.')
            return

        finally:
            return update_return

    def update_analysis_display(self, data):
        update_return = {'success': True}

        try:
            # UPDATE DISPLAY

            self.update_last['analysis'] = datetime.datetime.now()

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        except KeyboardInterrupt:
            logger.info('Exit signal received while updating trade display.')
            return

        finally:
            return update_return


if __name__ == '__main__':
    root = tk.Tk()
    app = Display(root, update_interval=1)
    root.mainloop()
    root.destroy()
