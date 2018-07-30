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

import tkinter as tk
from tkinter import ttk

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
        self.fonts['labelframes'] = ('Helvetica', 12, 'bold')

        self.colors = {'bg': {}, 'text': {}, 'transparent': None}
        self.colors['bg']['ready'] = 'green4'
        self.colors['bg']['updating'] = 'yellow'
        self.colors['bg']['warning'] = 'red'
        self.colors['bg']['buy'] = 'green2'
        self.colors['bg']['sell'] = 'red2'

        #### Variables ####
        self.variables = {
            'trade': {
                'price': tk.StringVar(),
                'quantity': tk.StringVar(),
                'amount': tk.StringVar()
            },
            'analysis': {
                'buys': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'difference': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    }
                },
                'sells': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'difference': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    }
                },
                'all': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    },
                    'difference': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar()
                    }
                }
            },
            'menu': {
                'status': tk.StringVar(),
                'exchange': tk.StringVar(),
                'market': tk.StringVar(),
                'interval': tk.StringVar()
            }
        }

        ## Give variables initial values ##
        # Menu Variables
        self.variables['menu']['status'].set('Updating')

        ## Combobox Selection Variables ##
        self.available_analysis = {}

        self.combobox_exchanges = None
        self.combobox_markets = None
        self.combobox_intervals = None

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
        self.root_frame = tk.Frame(self.root)

        self.trade_frame = {
            'master': tk.Frame(self.root_frame)
        }

        logger.debug('self.trade_frame: ' + str(self.trade_frame))

        self.analysis_frame = {
            'master': tk.Frame(self.root_frame),
            'buys': {
                'main': None,
                'current': None,
                'last': None,
                'difference': None
            },
            'sells': {
                'main': None,
                'current': None,
                'last': None,
                'difference': None
            },
            'all': {
                'main': None,
                'current': None,
                'last': None,
                'difference': None
            }
        }

        analysis_main_subframes = {
            'buys': {'main': tk.LabelFrame(self.analysis_frame['master'], text='Buys', font=self.fonts['labelframes'])},
            'sells': {'main': tk.LabelFrame(self.analysis_frame['master'], text='Sells', font=self.fonts['labelframes'])},
            'all': {'main': tk.LabelFrame(self.analysis_frame['master'], text='All', font=self.fonts['labelframes'])}
        }

        self.analysis_frame.update(analysis_main_subframes)

        for frame in self.analysis_frame:
            if frame != 'master':
                frame_update = {
                    'current': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Current', font=self.fonts['labelframes']),
                    'last': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Last', font=self.fonts['labelframes']),
                    'difference': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Difference', font=self.fonts['labelframes'])
                }
                self.analysis_frame[frame].update(frame_update)

        logger.debug('self.analysis_frame: ' + str(self.analysis_frame))

        self.menu_frame = {
            'master': tk.Frame(self.root_frame),
            'exchange': None,
            'market': None,
            'interval': None
        }

        menu_subframes = {
            'exchange': tk.LabelFrame(self.menu_frame['master'], text='Exchange'),
            'market': tk.LabelFrame(self.menu_frame['master'], text='Market'),
            'interval': tk.LabelFrame(self.menu_frame['master'], text='Interval')
        }

        self.menu_frame.update(menu_subframes)

        logger.debug('self.menu_frame: ' + str(self.menu_frame))

        #### Create Widgets ####
        # Create dictionary for widget storage
        self.widgets = {
            'trade': {
                'titles': {
                    'main': tk.Label(self.trade_frame['master'], text='Last Trade')
                },
                'text': {
                    'price': tk.Label(self.trade_frame['master'], text='Price:'),
                    'quantity': tk.Label(self.trade_frame['master'], text='Quantity:'),
                    'amount': tk.Label(self.trade_frame['master'], text='Amount:')
                },
                'variables': {
                    'price': tk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['price'], compound=tk.RIGHT),
                    'quantity': tk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['quantity']),
                    'amount': tk.Label(self.trade_frame['master'], textvariable=self.variables['trade']['amount'])
                }
            },
            'analysis': {
                'titles': {
                    'main': tk.Label(self.analysis_frame['master'], text='Analysis Info')
                },
                'buys': {
                    'current': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['current'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['current'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['current'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['current'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['last'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['difference'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['volume']),
                            'price': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['price']),
                            'amount': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['amount']),
                            'count': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['count'])
                        }
                    }
                },
                'sells': {
                    'current': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['sells']['current'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['sells']['current'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['sells']['current'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['sells']['current'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['sells']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['sells']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['sells']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['sells']['last'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['sells']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['sells']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['sells']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['sells']['difference'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['volume']),
                            'price': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['price']),
                            'amount': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['amount']),
                            'count': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['count'])
                        }
                    }
                },
                'all': {
                    'current': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['all']['current'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['all']['current'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['all']['current'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['all']['current'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['all']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['all']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['all']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['all']['last'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['all']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['all']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['all']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['all']['difference'], text='Count:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['volume']),
                            'price': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['price']),
                            'amount': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['amount']),
                            'count': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['count'])
                        }
                    }
                }
            },
            'menu': {
                'titles': {},
                'text': {},
                'variables': {
                    'status': tk.Label(self.menu_frame['master'], textvariable=self.variables['menu']['status'])
                },
                'buttons': {
                    'quit': tk.Button(self.menu_frame['master'], text='Quit', command=self.stop_display)
                },
                'comboboxes': {
                    'exchange': ttk.Combobox(
                        self.menu_frame['exchange'],
                        textvariable=self.variables['menu']['exchange'],
                        values=self.combobox_exchanges,
                        state='readonly'
                    ),
                    'market': ttk.Combobox(
                        self.menu_frame['market'],
                        textvariable=self.variables['menu']['market'],
                        values=self.combobox_markets,
                        state='readonly'
                    ),
                    'interval': ttk.Combobox(
                        self.menu_frame['interval'],
                        textvariable=self.variables['menu']['interval'],
                        values=self.combobox_intervals,
                        state='readonly'
                    )
                }
            }
        }

        # Save OS-dependent "transparent" background color name
        self.colors['transparent'] = self.widgets['trade']['titles']['main'].cget('bg')
        logger.debug('self.colors[\'transparent\']: ' + self.colors['transparent'])

        # Analysis Text Labels
        trade_types = ['buys', 'sells', 'all']
        categories = ['current', 'last', 'difference']

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
            logger.debug('frame: ' + frame)

            for category in self.widgets[frame]:
                logger.debug('category: ' + category)

                for element in self.widgets[frame][category]:
                    logger.debug('element: ' + element)

                    if frame == 'analysis' and category != 'titles':
                        for elem in self.widgets[frame][category][element]:
                            logger.debug('elem: ' + elem)

                            for e in self.widgets[frame][category][element][elem]:
                                logger.debug('e: ' + e)

                                selected_font = self.fonts[elem]
                                logger.debug('selected_font: ' + str(selected_font))

                                self.widgets[frame][category][element][elem][e].config(font=selected_font)

                    elif frame == 'analysis' and category == 'titles':
                        selected_font = self.fonts[category]
                        logger.debug('selected_font: ' + str(selected_font))

                        self.widgets[frame][category][element].config(font=selected_font)

                    #else:
                    elif frame != 'analysis':
                        selected_font = self.fonts[category]
                        logger.debug('selected_font: ' + str(selected_font))

                        self.widgets[frame][category][element].config(font=selected_font)

        #### Create Grid Layout ####

        ## Root Frame ##
        #self.root_frame.columnconfigure(0, weight=1)
        #self.root_frame.columnconfigure(1, weight=3)
        self.root_frame.grid()

        ## Trade Frames ##
        self.trade_frame['master'].grid(row=0, column=0)

        ## Analysis Frames ##

        # Analysis Master Frame
        self.analysis_frame['master'].grid(row=0, column=1)

        # Analysis Subframes
        self.analysis_frame['buys']['main'].grid(row=1, column=0)
        self.analysis_frame['sells']['main'].grid(row=1, column=1)
        self.analysis_frame['all']['main'].grid(row=1, column=2)

        self.analysis_frame['buys']['current'].grid(row=0, column=0)
        self.analysis_frame['buys']['last'].grid(row=1, column=0)
        self.analysis_frame['buys']['difference'].grid(row=2, column=0)

        self.analysis_frame['sells']['current'].grid(row=0, column=0)
        self.analysis_frame['sells']['last'].grid(row=1, column=0)
        self.analysis_frame['sells']['difference'].grid(row=2, column=0)

        self.analysis_frame['all']['current'].grid(row=0, column=0)
        self.analysis_frame['all']['last'].grid(row=1, column=0)
        self.analysis_frame['all']['difference'].grid(row=2, column=0)

        ## Menu Frames ##

        # Menu Master Frame
        self.menu_frame['master'].grid(row=1, column=0, columnspan=2)#, column=0, columnspan=2)

        # Menu Combobox Subframes
        self.menu_frame['exchange'].grid(row=0, column=1)
        self.menu_frame['market'].grid(row=0, column=2)
        self.menu_frame['interval'].grid(row=0, column=3)

        ### Widgets ###

        ## Trade Widgets ##

        # Trade Title Widgets
        self.widgets['trade']['titles']['main'].grid(row=0, columnspan=2)

        # Trade Text Widgets
        self.widgets['trade']['text']['price'].grid(row=1, column=0, sticky=tk.E)
        self.widgets['trade']['text']['quantity'].grid(row=2, column=0, sticky=tk.E)
        self.widgets['trade']['text']['amount'].grid(row=3, column=0, sticky=tk.E)

        # Trade Variable Widgets
        self.widgets['trade']['variables']['price'].grid(row=1, column=1, sticky=tk.W)
        self.widgets['trade']['variables']['quantity'].grid(row=2, column=1, sticky=tk.W)
        self.widgets['trade']['variables']['amount'].grid(row=3, column=1, sticky=tk.W)

        ## Analysis Widgets ##

        # Analysis Master Widgets
        self.widgets['analysis']['titles']['main'].grid(row=0, columnspan=3)

        # Analysis Category Widgets
        self.widgets['analysis']['buys']['current']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['buys']['current']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['buys']['current']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['buys']['current']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['buys']['last']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['buys']['last']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['buys']['last']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['buys']['last']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['buys']['difference']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['buys']['difference']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['buys']['difference']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['buys']['difference']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['sells']['current']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['sells']['current']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['sells']['current']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['sells']['current']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['sells']['last']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['sells']['last']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['sells']['last']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['sells']['last']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['sells']['difference']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['sells']['difference']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['sells']['difference']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['sells']['difference']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['all']['current']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['all']['current']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['all']['current']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['all']['current']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['all']['last']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['all']['last']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['all']['last']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['all']['last']['text']['count'].grid(row=3, column=0)
        self.widgets['analysis']['all']['difference']['text']['volume'].grid(row=0, column=0)
        self.widgets['analysis']['all']['difference']['text']['price'].grid(row=1, column=0)
        self.widgets['analysis']['all']['difference']['text']['amount'].grid(row=2, column=0)
        self.widgets['analysis']['all']['difference']['text']['count'].grid(row=3, column=0)

        self.widgets['analysis']['buys']['current']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['buys']['current']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['buys']['current']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['buys']['current']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['buys']['last']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['buys']['last']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['buys']['last']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['buys']['last']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['buys']['difference']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['buys']['difference']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['buys']['difference']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['buys']['difference']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['sells']['current']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['sells']['current']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['sells']['current']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['sells']['current']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['sells']['last']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['sells']['last']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['sells']['last']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['sells']['last']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['sells']['difference']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['sells']['difference']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['sells']['difference']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['sells']['difference']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['all']['current']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['all']['current']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['all']['current']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['all']['current']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['all']['last']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['all']['last']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['all']['last']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['all']['last']['variables']['count'].grid(row=3, column=1)
        self.widgets['analysis']['all']['difference']['variables']['volume'].grid(row=0, column=1)
        self.widgets['analysis']['all']['difference']['variables']['price'].grid(row=1, column=1)
        self.widgets['analysis']['all']['difference']['variables']['amount'].grid(row=2, column=1)
        self.widgets['analysis']['all']['difference']['variables']['count'].grid(row=3, column=1)

        # Menu Widgets
        self.widgets['menu']['variables']['status'].grid(row=0, column=0, padx=30, sticky=tk.SW)#row=4, column=0, columnspan=2, sticky=tk.E+tk.W)

        self.widgets['menu']['comboboxes']['exchange'].grid(row=0, column=0)
        self.widgets['menu']['comboboxes']['market'].grid(row=0, column=0)
        self.widgets['menu']['comboboxes']['interval'].grid(row=0, column=0)

        self.widgets['menu']['buttons']['quit'].grid(row=0, column=4, padx=30, sticky=tk.SE)

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

            self.combobox_exchanges = list(self.available_analysis.keys())
            for exch in self.combobox_exchanges:
                self.combobox_exchanges[self.combobox_exchanges.index(exch)] = exch.capitalize()
            logger.debug('self.combobox_exchanges: ' + str(self.combobox_exchanges))

            if self.variables['menu']['exchange'].get() == '':
                self.variables['menu']['exchange'].set(self.combobox_exchanges[0])
            elif self.variables['menu']['exchange'].get() not in self.combobox_exchanges:
                # HANDLE SITUATION WHERE DATA CEASES TO EXIST FOR CURRENT EXCHANGE SELECTION
                pass
            else:
                logger.info('Current Selection (Exchange): ' + self.variables['menu']['exchange'].get())

            self.combobox_markets = self.available_analysis[self.variables['menu']['exchange'].get().lower()]
            logger.debug('self.combobox_markets: ' + str(self.combobox_markets))

            if self.variables['menu']['market'].get() == '':
                self.variables['menu']['market'].set(self.combobox_markets[0])
            elif self.variables['menu']['markets'].get() not in self.combobox_markets:
                # HANDLE SITUATION WHERE DATA CEASES TO EXIST FOR CURRENT MARKET SELECTION
                pass
            else:
                logger.info('Current Selection (Market): ' + self.variables['menu']['market'].get())

            analysis_documents = db[collections['analysis']].find({'exchange': self.variables['menu']['exchange'].get().lower(),
                                                                   'market': self.variables['menu']['market'].get()})

            self.combobox_intervals = []

            for doc in analysis_documents:
                if doc['interval'] not in self.combobox_intervals:
                    self.combobox_intervals.append(doc['interval'])

            logger.debug('self.combobox_intervals: ' + str(self.combobox_intervals))

            if self.variables['menu']['interval'].get() == '':
                #self.variables['menu']['interval'].set(self.combobox_intervals[0])
                self.variables['menu']['interval'].set('1 hour')

                initialize_message = ('Initializing GUI with ' + self.variables['menu']['exchange'].get().capitalize() +
                                      '-' + self.variables['menu']['market'].get() + ' and an analysis interval of ' +
                                      self.variables['menu']['interval'].get() + '.')

                logger.info(initialize_message)
            elif self.variables['menu']['interval'].get() not in self.combobox_intervals:
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
        logger.debug('self.display_active: ' + str(self.display_active))

        logger.debug('Entering threading run loop.')

        while self.display_active == True:
            try:
                #logger.debug('self.display_active: ' + str(self.display_active))

                ## Update Trade Display Values ##
                #logger.debug('Updating trade display.')

                update_trade_result = self.update_trade_display()

                if update_trade_result['success'] == False:
                    logger.error('Error while updating trade display.')

                ## Update Analysis Display Values ##
                #logger.debug('Updating analysis display.')

                update_analysis_result = self.update_analysis_display()

                if update_analysis_result['success'] == False:
                    logger.error('Error while updating analysis display.')

                if self.gui_data_ready == False:
                    if self.trade_data_ready == True and self.analysis_data_ready == True:
                        self.variables['menu']['status'].set('Ready')
                        self.widgets['menu']['variables']['status'].configure(bg=self.colors['bg']['ready'])

                        self.gui_data_ready = True

                        logger.info('GUI data fully updated and ready for use.')

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

                    self.variables['menu']['status'].set(status_message)
                    """

                    time.sleep(0.1)

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

            # Match stage to retrieve documents for selected exchange and market
            match_pipeline = {'$match': {
                'exchange': self.variables['menu']['exchange'].get().lower(),
                'market': self.variables['menu']['market'].get()
            }}

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

            # Match stage to retrieve documents for selected exchange, market, and interval
            match_pipeline = {'$match': {
                'exchange': self.variables['menu']['exchange'].get().lower(),
                'market': self.variables['menu']['market'].get(),
                'interval': self.variables['menu']['interval'].get()
            }}

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

                pprint(analysis_last)

                #### Update Analysis Display Values ####

                ## Buys ##
                # Current
                self.variables['analysis']['buys']['current']['volume'].set("{:.0f}".format(analysis_last['current']['volume']['buy']))
                self.variables['analysis']['buys']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['buy']))
                self.variables['analysis']['buys']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['buy']))
                self.variables['analysis']['buys']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['buy']))

                # Last
                self.variables['analysis']['buys']['last']['volume'].set("{:.0f}".format(analysis_last['last']['volume']['buy']))
                self.variables['analysis']['buys']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['buy']))
                self.variables['analysis']['buys']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['buy']))
                self.variables['analysis']['buys']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['buy']))

                # Difference
                #self.variables['analysis']['buys']['difference']['volume'].set()
                #self.variables['analysis']['buys']['difference']['price'].set()
                #self.variables['analysis']['buys']['difference']['amount'].set()
                #elf.variables['analysis']['buys']['difference']['count'].set()

                ## Sells ##
                # Current
                self.variables['analysis']['sells']['current']['volume'].set("{:.0f}".format(analysis_last['current']['volume']['sell']))
                self.variables['analysis']['sells']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['sell']))
                self.variables['analysis']['sells']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['sell']))
                self.variables['analysis']['sells']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['sell']))

                # Last
                self.variables['analysis']['sells']['last']['volume'].set("{:.0f}".format(analysis_last['last']['volume']['sell']))
                self.variables['analysis']['sells']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['sell']))
                self.variables['analysis']['sells']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['sell']))
                self.variables['analysis']['sells']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['sell']))

                # Difference
                #self.variables['analysis']['sells']['difference']['volume'].set()
                #self.variables['analysis']['sells']['difference']['price'].set()
                #self.variables['analysis']['sells']['difference']['amount'].set()
                #self.variables['analysis']['sells']['difference']['count'].set()

                ## All ##
                # Current
                self.variables['analysis']['all']['current']['volume'].set("{:.0f}".format(analysis_last['current']['volume']['all']))
                self.variables['analysis']['all']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['all']))
                self.variables['analysis']['all']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['all']))
                self.variables['analysis']['all']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['all']))

                # Last
                self.variables['analysis']['all']['last']['volume'].set("{:.0f}".format(analysis_last['last']['volume']['all']))
                self.variables['analysis']['all']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['all']))
                self.variables['analysis']['all']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['all']))
                self.variables['analysis']['all']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['all']))

                # Difference
                #self.variables['analysis']['all']['difference']['volume'].set()
                #self.variables['analysis']['all']['difference']['price'].set()
                #self.variables['analysis']['all']['difference']['amount'].set()
                #self.variables['analysis']['all']['difference']['count'].set()

                self.update_last['analysis'] = datetime.datetime.now()

                if self.analysis_data_ready == False:
                    self.analysis_data_ready = True

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
