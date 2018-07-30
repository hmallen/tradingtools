import logging
import os
import sys

import configparser
import datetime
import json
from pprint import pprint
import time
import threading

from pymongo import MongoClient

#import tkinter as tk
#from tkinter import ttk
from tkinter import *
from tkinter import ttk
import tkinter as tk

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

        self.images = {'trade': {}, 'analysis': {}}
        self.images['trade']['arrow_buy'] = tk.PhotoImage(file='resources/gui/arrow_buy_small.gif')
        self.images['trade']['arrow_sell'] = tk.PhotoImage(file='resources/gui/arrow_sell_small.gif')

        self.fonts = {}
        self.fonts['titles'] = ('Helvetica', 12, 'bold')
        self.fonts['text'] = ('Helvetica', 10, 'bold')
        self.fonts['variables'] = ('Helvetica', 10)
        self.fonts['menus'] = ('Helvetica', 10)

        self.colors = {'bg': {}, 'text': {}, 'transparent': None}
        self.colors['bg']['ready'] = 'green4'
        self.colors['bg']['updating'] = 'yellow'
        self.colors['bg']['warning'] = 'red'
        self.colors['bg']['buy'] = 'green2'
        self.colors['bg']['sell'] = 'red2'

        #### Variables ####
        self.variables = {'trade': {}, 'analysis': {}, 'menu': {}}

        ## Trade Frame ##
        # Create dynamically updating GUI variables
        self.variables['trade']['price'] = tk.StringVar()
        self.variables['trade']['quantity'] = tk.StringVar()
        self.variables['trade']['amount'] = tk.StringVar()
        self.variables['trade']['status'] = tk.StringVar()
        # Give variables initial values
        self.variables['trade']['price'].set('N/A')
        self.variables['trade']['quantity'].set('N/A')
        self.variables['trade']['amount'].set('N/A')
        self.variables['trade']['status'].set('Updating')

        ## Analysis Frame ##
        # Variables
        #

        # Initial Values
        #

        ## Combobox Selections ##
        self.available_analysis = {}

        self.available_exchanges = None
        self.available_markets = None
        self.available_intervals = None

        self.variables['menu']['exchange'] = tk.StringVar()
        self.variables['menu']['market'] = tk.StringVar()
        self.variables['menu']['interval'] = tk.StringVar()

        logger.info('Gathering available exchange, market, and interval information.')

        update_available_result = self.update_available_analysis()

        if update_available_result['success'] == False:
            logger.error('Error while updating available analysis exchanges and markets. Exiting.')
            sys.exit(1)

        self.update_last = {'trade': None, 'analysis': None, 'menu': None}

        self.create_widgets()

        self.start()

    def create_widgets(self):
        """
        - Title (Exchange/Market)
        - Subheading (Backtest interval)
        - Data display
        - Quit button
        """

        ### Create Frames ####
        self.trade_frame = {
            'master': ttk.Frame(self.root)
        }

        logger.debug('self.trade_frame: ' + str(self.trade_frame))

        self.analysis_frame = {
            'master': ttk.Frame(self.root),
            'buys': None,
            'sells': None,
            'all': None
        }

        analysis_main_subframes = {
            'buys': {
                'main': ttk.LabelFrame(self.analysis_frame['master'], text='Buys')
            },
            'sells': {
                'main': ttk.LabelFrame(self.analysis_frame['master'], text='Sells')
            },
            'all': {
                'main': ttk.LabelFrame(self.analysis_frame['master'], text='All')
            }
        }

        self.analysis_frame.update(analysis_main_subframes)

        analysis_period_subframes = {
            'buys': {
                'current': ttk.LabelFrame(self.analysis_frame['buys']['main'], text='Current'),
                'last': ttk.LabelFrame(self.analysis_frame['buys']['main'], text='Last'),
                'difference': ttk.LabelFrame(self.analysis_frame['buys']['main'], text='Difference')
            },
            'sells': {
                'current': ttk.LabelFrame(self.analysis_frame['sells']['main'], text='Current'),
                'last': ttk.LabelFrame(self.analysis_frame['sells']['main'], text='Last'),
                'difference': ttk.LabelFrame(self.analysis_frame['sells']['main'], text='Difference')
            },
            'all': {
                'current': ttk.LabelFrame(self.analysis_frame['all']['main'], text='Current'),
                'last': ttk.LabelFrame(self.analysis_frame['all']['main'], text='Last'),
                'difference': ttk.LabelFrame(self.analysis_frame['all']['main'], text='Difference')
            }
        }

        self.analysis_frame.update(analysis_period_subframes)

        logger.debug('self.analysis_frame: ' + str(self.analysis_frame))

        self.menu_frame = {
            'master': ttk.Frame(self.root)
        }

        logger.debug('self.menu_frame: ' + str(self.menu_frame))

        #### Create Widgets ####
        # Create dictionary for widget storage
        self.widgets = {'trade': {'titles': {}, 'text': {}, 'variables': {}},
                        'analysis': {
                            'titles': {},
                            'buys': {'titles': {}, 'text': {}, 'variables': {}},
                            'sells': {'titles': {}, 'text': {}, 'variables': {}},
                            'all': {'titles': {}, 'text': {}, 'variables': {}}
                        },
                        'menu': {'titles': {}, 'text': {}, 'variables': {},
                                 'buttons': {}, 'listboxes': {}, 'comboboxes': {}}}

        ## Trade Frame ##
        # Trade Titles
        self.widgets['trade']['titles']['main'] = ttk.Label(self.trade_frame['master'], text='Last Trade')

        self.colors['transparent'] = self.widgets['trade']['titles']['main'].cget('bg')   # Save OS-dependent "transparent" background color name
        logger.debug('self.colors[\'transparent\']: ' + self.colors['transparent'])

        # Trade Text Labels
        self.widgets['trade']['text']['price'] = ttk.Label(self.trade_frame['master'], text='Price:')
        self.widgets['trade']['text']['quantity'] = ttk.Label(self.trade_frame['master'], text='Quantity:')
        self.widgets['trade']['text']['amount'] = ttk.Label(self.trade_frame['master'], text='Amount:')

        # Trade Variables
        self.widgets['trade']['variables']['price'] = ttk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['price'], compound=ttk.RIGHT)
        self.widgets['trade']['variables']['quantity'] = ttk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['quantity'])
        self.widgets['trade']['variables']['amount'] = ttk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['amount'])

        ## Analysis Frame ##
        # Analysis Titles
        self.widgets['analysis']['titles']['main'] = ttk.Label(self.analysis_frame['master'], text='Analysis Info')

        # Analysis Text Labels
        trade_types = ['buys', 'sells', 'all']
        categories = ['current', 'last', 'difference']

        for trade_type in trade_types:
            logger.debug('trade_type: ' + trade_type)

            for category in categories:
                logger.debug('category: ' + category)

                """
                self.widgets['analysis'][trade_type][category]['text']['volume']
                self.widgets['analysis'][trade_type][category]['text']['price']
                self.widgets['analysis'][trade_type][category]'text']['amount']
                self.widgets['analysis'][trade_type][category]'text']['count']
                self.widgets['analysis'][trade_type][category]'text']['rate_volume']
                self.widgets['analysis'][trade_type][category]'text']['rate_amount']
                self.widgets['analysis'][trade_type][category]'text']['rate_count']

                self.widgets['analysis'][trade_type][category]'variables']['volume']
                self.widgets['analysis'][trade_type][category]'variables']['price']
                self.widgets['analysis'][trade_type][category]'variables']['amount']
                self.widgets['analysis'][trade_type][category]'variables']['count']
                self.widgets['analysis'][trade_type][category]'variables']['rate_volume']
                self.widgets['analysis'][trade_type][category]'variables']['rate_amount']
                self.widgets['analysis'][trade_type][category]'variables']['rate_count']
                """

        ## Menu Frame ##
        # Status
        self.widgets['menu']['variables']['status'] = ttk.Label(self.menu_frame['master'], textvariable=self.variables['trade']['status'])

        # Buttons
        self.widgets['menu']['buttons']['quit'] = ttk.Button(self.menu_frame['master'], text='Quit', command=self.stop_display)

        # Comboboxes
        self.widgets['menu']['comboboxes']['exchange'] = ttk.Combobox(self.menu_frame['master'], textvariable=self.variables['menu']['exchange'], values=self.available_exchanges)
        self.widgets['menu']['comboboxes']['market'] = ttk.Combobox(self.menu_frame['master'], textvariable=self.variables['menu']['market'], values=self.available_markets)
        self.widgets['menu']['comboboxes']['interval'] = ttk.Combobox(self.menu_frame['master'], textvariable=self.variables['menu']['interval'], values=self.available_intervals)

        #for combo in self.widgets['menu']['comboboxes']:
            #pass

        """
        def OptionCallBack(*args):
            print variable.get()
            print so.current()

        variable = StringVar(app)
        variable.set("Select From List")
        variable.trace('w', OptionCallBack)


        so = ttk.Combobox(app, textvariable=variable)
        so.config(values =('Tracing Upstream', 'Tracing Downstream','Find Path'))
        so.grid(row=1, column=4, sticky='E', padx=10)
        """

        ## Format Text ##
        formatting_frames = ['trade', 'analysis']

        for frame in formatting_frames:
            for category in self.widgets[frame]:
                logger.debug('category: ' + category)

                for element in self.widgets[frame][category]:
                    logger.debug('element: ' + element)

                    if frame == 'analysis' and category != 'titles':
                        for elem in self.widgets[frame][category][element]:
                            logger.debug('elem: ' + elem)

                            selected_font = self.fonts[elem]
                            logger.debug('selected_font: ' + str(selected_font))

                            self.widgets[frame][category][element][elem].config(font=selected_font)

                            if category == 'variables':
                                self.widgets[frame][category][element][elem].config(bg=self.colors['bg']['updating'])

                    else:
                        selected_font = self.fonts[category]
                        logger.debug('selected_font: ' + str(selected_font))

                        self.widgets[frame][category][element].config(font=selected_font)

                        if category == 'variables':
                            self.widgets[frame][category][element].config(bg=self.colors['bg']['updating'])

        ## Create Grid Layout ##
        # Frames
        self.trade_frame['master'].grid(row=0, column=0)
        self.analysis_frame['master'].grid(row=0, column=1)
        self.menu_frame['master'].grid(row=1)#, column=0, columnspan=2)

        # Trade Frame
        self.widgets['trade']['titles']['main'].grid(row=0, columnspan=2)

        self.widgets['trade']['text']['price'].grid(row=1, column=0, sticky=tk.E); self.widgets['trade']['variables']['price'].grid(row=1, column=1, sticky=tk.W)
        self.widgets['trade']['text']['quantity'].grid(row=2, column=0, sticky=tk.E); self.widgets['trade']['variables']['quantity'].grid(row=2, column=1, sticky=tk.W)
        self.widgets['trade']['text']['amount'].grid(row=3, column=0, sticky=tk.E); self.widgets['trade']['variables']['amount'].grid(row=3, column=1, sticky=tk.W)

        # Analysis Frame
        self.widgets['analysis']['titles']['main'].grid(row=0, columnspan=2)

        # Menus Frame
        self.widgets['menu']['variables']['status'].grid(row=0, column=0)#, sticky=tk.W)#row=4, column=0, columnspan=2, sticky=tk.E+tk.W)
        self.widgets['menu']['buttons']['quit'].grid(row=0, column=1)#, sticky=tk.E)

        self.widgets['menu']['comboboxes']['exchange'].grid(row=0, column=2)
        self.widgets['menu']['comboboxes']['market'].grid(row=0, column=3)
        self.widgets['menu']['comboboxes']['interval'].grid(row=0, column=4)

        # Variables to signal state of data
        self.trade_data_ready = False
        self.analysis_data_ready = False
        self.gui_data_ready = False

    def update_available_analysis(self):
        update_markets_return = {'success': True}

        try:
            analysis_documents = db[collections['analysis']].find({})

            for doc in analysis_documents:
                if doc['exchange'] not in self.available_analysis:
                    self.available_analysis[doc['exchange']] = []

                if doc['market'] not in self.available_analysis[doc['exchange']]:
                    self.available_analysis[doc['exchange']].append(doc['market'])

            self.available_exchanges = list(self.available_analysis.keys())
            for exch in self.available_exchanges:
                self.available_exchanges[self.available_exchanges.index(exch)] = exch.capitalize()
            logger.debug('self.available_exchanges: ' + str(self.available_exchanges))

            if self.variables['menu']['exchange'].get() == '':
                self.variables['menu']['exchange'].set(self.available_exchanges[0])
            elif self.variables['menu']['exchange'].get() not in self.available_exchanges:
                # HANDLE SITUATION WHERE DATA CEASES TO EXIST FOR CURRENT EXCHANGE SELECTION
                pass
            else:
                logger.info('Current Selection (Exchange): ' + self.variables['menu']['exchange'].get())

            self.available_markets = self.available_analysis[self.variables['menu']['exchange'].get().lower()]
            logger.debug('self.available_markets: ' + str(self.available_markets))

            if self.variables['menu']['market'].get() == '':
                self.variables['menu']['market'].set(self.available_markets[0])
            elif self.variables['menu']['markets'].get() not in self.available_markets:
                # HANDLE SITUATION WHERE DATA CEASES TO EXIST FOR CURRENT MARKET SELECTION
                pass
            else:
                logger.info('Current Selection (Market): ' + self.variables['menu']['market'].get())

            analysis_documents = db[collections['analysis']].find({'exchange': self.variables['menu']['exchange'].get().lower(),
                                                                   'market': self.variables['menu']['market'].get()})

            self.available_intervals = []

            for doc in analysis_documents:
                if doc['interval'] not in self.available_intervals:
                    self.available_intervals.append(doc['interval'])

            logger.debug('self.available_intervals: ' + str(self.available_intervals))

            if self.variables['menu']['interval'].get() == '':
                #self.variables['menu']['interval'].set(self.available_intervals[0])
                self.variables['menu']['interval'].set('1 hour')

                initialize_message = ('Initializing GUI with ' + self.variables['menu']['exchange'].get().capitalize() +
                                      '-' + self.variables['menu']['market'].get() + ' and an analysis interval of ' +
                                      self.variables['menu']['interval'].get() + '.')

                logger.info(initialize_message)
            elif self.variables['menu']['interval'].get() not in self.available_intervals:
                # HANDLE SITUATION WHERE DATA CEASES TO EXIST FOR CURRENT INTERVAL SELECTION
                pass
            else:
                logger.info('Current Selection (Interval): ' + self.variables['menu']['interval'].get())

        except Exception as e:
            logger.exception(e)

            update_markets_return['success'] = False

        finally:
            return update_markets_return

    def stop_display(self):
        self.display_active = False
        #self.root.quit()
        #self.root.update()
        #self.root.destroy()

    def run(self):
        self.display_active = True

        while self.display_active == True:
            try:
                #logger.debug('self.display_active: ' + str(self.display_active))

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

                ## Update Trade Display Values ##
                #logger.debug('Updating trade display.')

                update_trade_result = self.update_trade_display()

                if update_trade_result['success'] == False:
                    logger.error('Error while updating trade display.')

                ## Update Analysis Display Values ##
                #logger.debug('Updating analysis display.')

                #update_analysis_result = self.update_analysis_display()

                #if update_analysis_result['success'] == False:
                    #logger.error('Error while updating analysis display.')

                if self.gui_data_ready == False:
                    if self.trade_data_ready == True and self.analysis_data_ready == True:
                        self.variables['trade']['status'].set('Ready')

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

        self.root.quit()

        logger.debug('Exited main display loop.')

    def update_trade_display(self):
        update_return = {'success': True}

        try:
            ## Get most recent trade info from database ##
            #logger.debug('Retrieving most recent trade from database.')

            trade_pipeline = []

            # Sort stage to order with most recent trade first
            sort_pipeline = {'$sort': {'_id': -1}}
            trade_pipeline.append(sort_pipeline)

            # Limit stage to retrieve only most recent trade
            limit_pipeline = {'$limit': 1}
            trade_pipeline.append(limit_pipeline)

            # Run aggregation pipeline
            #logger.debug('trade_pipeline: ' + str(trade_pipeline))

            aggregate_result = db.command('aggregate', collections['data'], cursor={}, pipeline=trade_pipeline)

            #logger.debug('aggregate_result[\'ok\']: ' + str(aggregate_result['ok']))

            if aggregate_result['ok'] == 1:
                trade_last = aggregate_result['cursor']['firstBatch'][0]

                #pprint(trade_last)

                # Update display values
                self.variables['trade']['price'].set("{:.8f}".format(trade_last['price']) + ' ')# + data['quote_currency'] + '/' + data['trade_currency'] + ' ')
                self.variables['trade']['quantity'].set("{:.0f}".format(trade_last['quantity']) + ' ' + trade_last['trade_currency'])
                self.variables['trade']['amount'].set("{:.8f}".format(trade_last['price'] * trade_last['quantity']) + ' ' + trade_last['quote_currency'])
                if trade_last['side'] == 'buy':
                    self.widgets['trade']['variables']['price'].config(image=self.images['trade']['arrow_buy'])
                else:
                    self.widgets['trade']['variables']['price'].config(image=self.images['trade']['arrow_sell'])

                self.update_last['trade'] = datetime.datetime.now()

                if self.trade_data_ready == False:
                    self.trade_data_ready = True

                    for var in self.widgets['trade']['variables']:
                        #if var != 'side':
                        if var == 'status':
                            selected_color = self.colors['bg']['ready']
                        else:
                            selected_color = self.colors['transparent']
                        logger.debug('selected_color: ' + selected_color)

                        self.widgets['trade']['variables'][var].config(bg=selected_color)

            else:
                logger.error('Error returned from aggregation pipeline while retrieving most recent trade document.')

                update_result['success'] = False

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        except KeyboardInterrupt:
            logger.info('Exit signal received while updating trade display.')

        finally:
            return update_return

    def update_analysis_display(self):
        update_return = {'success': True}

        try:
            ## Get most recent analysis info from database ##
            #logger.debug('Retrieving most recent analysis from database.')

            analysis_pipeline = []

            # Sort stage to order with most recent analysis first
            sort_pipeline = {'$sort': {'time': -1}}
            analysis_pipeline.append(sort_pipeline)

            # Limit stage to retrieve only most recent analysis
            limit_pipeline = {'$limit': 1}
            analysis_pipeline.append(limit_pipeline)

            # Run aggregation pipeline
            #logger.debug('analysis_pipeline: ' + str(analysis_pipeline))

            aggregate_result = db.command('aggregate', collections['analysis'], cursor={}, pipeline=analysis_pipeline)

            #logger.debug('aggregate_result[\'ok\']: ' + str(aggregate_result['ok']))

            if aggregate_result['ok'] == 1:
                analysis_last = aggregate_result['cursor']['firstBatch'][0]

                #pprint(analysis_last)

                # Update GUI with recent analysis info
                # VALUES
                # VALUES
                # VALUES
                # VALUES

                self.update_last['analysis'] = datetime.datetime.now()

                if self.analysis_data_ready == False: self.analysis_data_ready = True

            else:
                logger.error('Error returned from aggregation pipeline while retrieving most recent analysis document.')

        except Exception as e:
            logger.exception(e)

            update_return['success'] = False

        except KeyboardInterrupt:
            logger.info('Exit signal received while updating trade display.')
            return

        finally:
            return update_return

    def get_widget_attributes(self):
        all_widgets = self.root.winfo_children()
        for widg in all_widgets:
            print('\nWidget Name: {}'.format(widg.winfo_class()))
            keys = widg.keys()
            for key in keys:
                print("Attribute: {:<20}".format(key), end=' ')
                value = widg[key]
                vtype = type(value)
                print('Type: {:<30} Value: {}'.format(str(vtype), value))


def main():
    root = tk.Tk()
    display = Display(root, update_interval=1)
    display.get_widget_attributes()
    root.mainloop()
    root.destroy()


if __name__ == '__main__':
    main()
