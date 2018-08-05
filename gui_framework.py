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

from binance.client import Client as BinanceClient
from binance.depthcache import DepthCacheManager
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

import tkinter as tk
from tkinter import font
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

collections = {
    'data': config['mongodb']['collection_data'],
    'analysis': config['mongodb']['collection_analysis'],
    'candles': config['mongodb']['collection_candles']
}

binance_api = config['binance']['api']
binance_secret = config['binance']['secret']

binance_client = BinanceClient(binance_api, binance_secret)


class Display(threading.Thread):

    def __init__(self, master=None, trade_update_interval=1, analysis_update_interval=10):
        self.root = master

        self.trade_update_interval = trade_update_interval
        self.analysis_update_interval = analysis_update_interval

        threading.Thread.__init__(self)

        self.images = {'trade': {}, 'analysis': {}}
        self.images['trade']['arrow_buy'] = tk.PhotoImage(file='resources/gui/arrow_buy_small.gif')
        self.images['trade']['arrow_sell'] = tk.PhotoImage(file='resources/gui/arrow_sell_small.gif')

        self.ttk_style = ttk.Style()
        self.ttk_style.theme_use('clam')
        self.ttk_style.configure('neutral.Horizontal.TProgressbar', foreground='grey', background='grey')
        self.ttk_style.configure('red.Horizontal.TProgressbar', foreground='red3', background='red3')
        self.ttk_style.configure('green.Horizontal.TProgressbar', foreground='green3', background='green3')

        self.fonts = {
            'trade': {
                'titles': font.Font(family='Helvetica', size=13, weight='bold', underline=0),
                'text': font.Font(family='Helvetica', size=11, weight='bold'),
                'variables': font.Font(family='Helvetica', size=9),
                'labelframes': {
                    'main': font.Font(family='Helvetica', size=11, weight='bold'),
                    'sub': font.Font(family='Helvetica', size=9, weight='bold')
                },
                'progressbar': {
                    'value': font.Font(family='Helvetica', size=11, weight='bold'),
                    'change': font.Font(family='Helvetica', size=11)
                }
            },
            'analysis': {
                'titles': font.Font(family='Helvetica', size=13, weight='bold', underline=1),
                'text': font.Font(family='Helvetica', size=9, weight='bold'),
                'variables': font.Font(family='Helvetica', size=9),
                'labelframes': {
                    'main': font.Font(family='Helvetica', size=11, weight='bold'),
                    'sub': font.Font(family='Helvetica', size=9, weight='bold')
                }
            }
        }

        self.colors = {'bg': {}, 'text': {}, 'transparent': None}
        self.colors['bg']['ready'] = 'green4'
        self.colors['bg']['updating'] = 'yellow'
        self.colors['bg']['warning'] = 'red'
        self.colors['bg']['positive'] = 'green2'
        self.colors['bg']['negative'] = 'red2'
        self.colors['bg']['orderbook'] = {
            'asks': 'tomato',
            'bids': 'sea green'
        }

        #### Variables ####
        self.variables = {
            'trade': {
                'active_market': {
                    'exchange_market': tk.StringVar(),
                    'interval': tk.StringVar()
                },
                'last_trade': {
                    'price': tk.StringVar(),
                    'quantity': tk.StringVar(),
                    'amount': tk.StringVar()
                },
                'orderbook': {
                    'bids': tk.StringVar(),
                    'asks': tk.StringVar()
                },
                'differential': {
                    'value': tk.DoubleVar(),
                    'change': tk.StringVar()
                }
            },
            'analysis': {
                'buys': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'difference': {
                        'volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'price': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        }
                    }
                },
                'sells': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'difference': {
                        'volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'price': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        }
                    }
                },
                'all': {
                    'current': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'last': {
                        'volume': tk.StringVar(),
                        'price': tk.StringVar(),
                        'amount': tk.StringVar(),
                        'count': tk.StringVar(),
                        'rate_volume': tk.StringVar(),
                        'rate_amount': tk.StringVar(),
                        'rate_count': tk.StringVar()
                    },
                    'difference': {
                        'volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'price': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_volume': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_amount': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        },
                        'rate_count': {
                            'absolute': tk.StringVar(),
                            'percent': tk.StringVar()
                        }
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

        # Variables to signal state of data
        self.trade_data_ready = False
        self.analysis_data_ready = False
        self.gui_data_ready = False

        self.update_last = {'trade': None, 'analysis': None, 'menu': None}

        # Trace Combobox Variables and Route to Callback Function
        self.variables['menu']['exchange'].trace('w', self.combobox_trace)
        self.variables['menu']['market'].trace('w', self.combobox_trace)
        self.variables['menu']['interval'].trace('w', self.combobox_trace)

        # Orderbook Variables and Route to Callback Function
        #self.variables['trade']['orderbook']['bids'].trace('w', self.orderbook_trace)
        #self.variables['trade']['orderbook']['asks'].trace('w', self.orderbook_trace)

        # Give variables initial values
        self.variables['trade']['orderbook']['asks'].set('Updating')
        self.variables['trade']['orderbook']['bids'].set('Updating')

        self.variables['trade']['differential']['value'].set(50.0)
        self.variables['trade']['differential']['change'].set('N/A')

        self.variables['menu']['status'].set('Updating')

        ## Combobox Selection Variables ##
        self.available_analysis = {}

        self.combobox_exchanges = None
        self.combobox_markets = None
        self.combobox_intervals = None

        # Binance Websocket-based Features
        self.binance_dcm = None

        logger.info('Gathering available exchange, market, and interval information.')

        process_combobox_result = self.process_combobox_selections()

        if process_combobox_result['success'] == False:
            logger.error('Error while updating available analysis exchanges and markets. Exiting.')
            sys.exit(1)

        self.create_widgets()

        self.start()

    def create_widgets(self):
        """
        - Title (Exchange/Market)
        - Subheading (Backtest interval)
        - Data display
        - Quit button
        """

        #### Define TTK Styles ####
        #progressbar_style = ttk.Style()
        #progressbar_style.config('Horizontal.TProgressbar')

        #### Create Frames ####
        self.trade_frame = {
            'master': tk.Frame(self.root)
        }

        trade_subframes = {
            'active_market': tk.Frame(self.trade_frame['master']),
            'last_trade': tk.LabelFrame(self.trade_frame['master'], text='Last Trade', font=self.fonts['trade']['labelframes']['main']),
            'orderbook': {
                'main': tk.LabelFrame(self.trade_frame['master'], text='Orderbook', font=self.fonts['trade']['labelframes']['main']),
                'asks': None,
                'bids': None
            },
            'differential': tk.LabelFrame(self.trade_frame['master'], text='Differential', font=self.fonts['trade']['labelframes']['main'])
        }

        self.trade_frame.update(trade_subframes)

        orderbook_subframes = {
            'asks': tk.LabelFrame(self.trade_frame['orderbook']['main'], text='Asks', font=self.fonts['trade']['labelframes']['sub'], bd=0, labelanchor=tk.NW),
            'bids': tk.LabelFrame(self.trade_frame['orderbook']['main'], text='Bids', font=self.fonts['trade']['labelframes']['sub'], bd=0, labelanchor=tk.SW)
        }

        self.trade_frame['orderbook'].update(orderbook_subframes)

        logger.debug('self.trade_frame: ' + str(self.trade_frame))

        self.analysis_frame = {
            'master': tk.Frame(self.root),
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
            'buys': {'main': tk.LabelFrame(self.analysis_frame['master'], text='Buys', font=self.fonts['analysis']['labelframes']['main'])},
            'sells': {'main': tk.LabelFrame(self.analysis_frame['master'], text='Sells', font=self.fonts['analysis']['labelframes']['main'])},
            'all': {'main': tk.LabelFrame(self.analysis_frame['master'], text='All', font=self.fonts['analysis']['labelframes']['main'])}
        }

        self.analysis_frame.update(analysis_main_subframes)

        for frame in self.analysis_frame:
            if frame != 'master':
                frame_update = {
                    'current': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Current', font=self.fonts['analysis']['labelframes']['sub']),
                    'last': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Last', font=self.fonts['analysis']['labelframes']['sub']),
                    'difference': tk.LabelFrame(self.analysis_frame[frame]['main'], text='Difference', font=self.fonts['analysis']['labelframes']['sub'])
                }
                self.analysis_frame[frame].update(frame_update)

        logger.debug('self.analysis_frame: ' + str(self.analysis_frame))

        self.menu_frame = {
            'master': tk.Frame(self.root),
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
                'active_market': {
                    'titles': {
                        'exchange_market': tk.Label(self.trade_frame['active_market'], textvariable=self.variables['trade']['active_market']['exchange_market'])
                    },
                    'text': {
                        'interval': tk.Label(self.trade_frame['active_market'], textvariable=self.variables['trade']['active_market']['interval'])
                    },
                    'variables': {}
                },
                'last_trade': {
                    'titles': {},
                    'text': {
                        'price': tk.Label(self.trade_frame['last_trade'], text='Price:'),
                        'quantity': tk.Label(self.trade_frame['last_trade'], text='Quantity:'),
                        'amount': tk.Label(self.trade_frame['last_trade'], text='Amount:')
                    },
                    'variables': {
                        'price': tk.Label(self.trade_frame['last_trade'], textvariable=self.variables['trade']['last_trade']['price'], compound=tk.RIGHT),
                        'quantity': tk.Label(self.trade_frame['last_trade'], textvariable=self.variables['trade']['last_trade']['quantity']),
                        'amount': tk.Label(self.trade_frame['last_trade'], textvariable=self.variables['trade']['last_trade']['amount'])
                    }
                },
                'orderbook': {
                    'titles': {},
                    'text': {},
                    'variables': {
                        'bids': tk.Label(
                            self.trade_frame['orderbook']['bids'],
                            textvariable=self.variables['trade']['orderbook']['bids'],
                            bg=self.colors['bg']['updating'],
                            justify=tk.LEFT,
                            #anchor=tk.W,
                            #width=20
                        ),
                        'asks': tk.Label(
                            self.trade_frame['orderbook']['asks'],
                            textvariable=self.variables['trade']['orderbook']['asks'],
                            bg=self.colors['bg']['updating'],
                            justify=tk.LEFT,
                            #anchor=tk.W,
                            #width=20
                        )
                    }#,
                    #'separator': ttk.Separator(self.trade_frame['orderbook']['main'], orient=tk.HORIZONTAL)
                },
                'differential': {
                    'progressbar': ttk.Progressbar(
                        self.trade_frame['differential'],
                        style='neutral.Horizontal.TProgressbar',
                        mode='determinate',
                        orient=tk.HORIZONTAL,
                        length=150,
                        variable=self.variables['trade']['differential']['value']
                    ),
                    'text': {
                        'value': tk.Label(self.trade_frame['differential'], textvariable=self.variables['trade']['differential']['value'], font=self.fonts['trade']['progressbar']['value']),
                        'change': tk.Label(self.trade_frame['differential'], textvariable=self.variables['trade']['differential']['change'], font=self.fonts['trade']['progressbar']['change'])
                    }
                }
            },
            'analysis': {
                'titles': {
                    'main': tk.Label(self.analysis_frame['master'], text='Flow Rate Analysis')
                },
                'buys': {
                    'current': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['current'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['current'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['current'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['current'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['buys']['current'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['buys']['current'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['buys']['current'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['buys']['current'], textvariable=self.variables['analysis']['buys']['current']['rate_count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['last'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['buys']['last'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['buys']['last'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['buys']['last'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['buys']['last'], textvariable=self.variables['analysis']['buys']['last']['rate_count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['buys']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['buys']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['buys']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['buys']['difference'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['buys']['difference'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['buys']['difference'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['buys']['difference'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['volume']['percent'])
                            },
                            'price': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['price']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['price']['percent'])
                            },
                            'amount': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['amount']['percent'])
                            },
                            'count': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['count']['percent'])
                            },
                            'rate_volume': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_volume']['percent'])
                            },
                            'rate_amount': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_amount']['percent'])
                            },
                            'rate_count': {
                                'absolute': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['buys']['difference'], textvariable=self.variables['analysis']['buys']['difference']['rate_count']['percent'])
                            }
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
                            'count': tk.Label(self.analysis_frame['sells']['current'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['sells']['current'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['sells']['current'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['sells']['current'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['sells']['current'], textvariable=self.variables['analysis']['sells']['current']['rate_count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['sells']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['sells']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['sells']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['sells']['last'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['sells']['last'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['sells']['last'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['sells']['last'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['sells']['last'], textvariable=self.variables['analysis']['sells']['last']['rate_count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['sells']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['sells']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['sells']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['sells']['difference'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['sells']['difference'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['sells']['difference'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['sells']['difference'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['volume']['percent'])
                            },
                            'price': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['price']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['price']['percent'])
                            },
                            'amount': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['amount']['percent'])
                            },
                            'count': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['count']['percent'])
                            },
                            'rate_volume': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_volume']['percent'])
                            },
                            'rate_amount': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_amount']['percent'])
                            },
                            'rate_count': {
                                'absolute': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['sells']['difference'], textvariable=self.variables['analysis']['sells']['difference']['rate_count']['percent'])
                            }
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
                            'count': tk.Label(self.analysis_frame['all']['current'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['all']['current'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['all']['current'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['all']['current'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['volume']),
                            'price': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['price']),
                            'amount': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['amount']),
                            'count': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['all']['current'], textvariable=self.variables['analysis']['all']['current']['rate_count'])
                        }
                    },
                    'last': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['all']['last'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['all']['last'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['all']['last'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['all']['last'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['all']['last'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['all']['last'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['all']['last'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['volume']),
                            'price': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['price']),
                            'amount': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['amount']),
                            'count': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['count']),
                            'rate_volume': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['rate_volume']),
                            'rate_amount': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['rate_amount']),
                            'rate_count': tk.Label(self.analysis_frame['all']['last'], textvariable=self.variables['analysis']['all']['last']['rate_count'])
                        }
                    },
                    'difference': {
                        'titles': {},
                        'text': {
                            'volume': tk.Label(self.analysis_frame['all']['difference'], text='Volume:'),
                            'price': tk.Label(self.analysis_frame['all']['difference'], text='Price Avg:'),
                            'amount': tk.Label(self.analysis_frame['all']['difference'], text='Amount:'),
                            'count': tk.Label(self.analysis_frame['all']['difference'], text='Count:'),
                            'rate_volume': tk.Label(self.analysis_frame['all']['difference'], text='Vol. Rate:'),
                            'rate_amount': tk.Label(self.analysis_frame['all']['difference'], text='Amt. Rate:'),
                            'rate_count': tk.Label(self.analysis_frame['all']['difference'], text='Count Rate:')
                        },
                        'variables': {
                            'volume': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['volume']['percent'])
                            },
                            'price': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['price']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['price']['percent'])
                            },
                            'amount': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['amount']['percent'])
                            },
                            'count': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['count']['percent'])
                            },
                            'rate_volume': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_volume']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_volume']['percent'])
                            },
                            'rate_amount': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_amount']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_amount']['percent'])
                            },
                            'rate_count': {
                                'absolute': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_count']['absolute']),
                                'percent': tk.Label(self.analysis_frame['all']['difference'], textvariable=self.variables['analysis']['all']['difference']['rate_count']['percent'])
                            }
                        }
                    }
                }
            },
            'menu': {
                'titles': {},
                'text': {},
                'variables': {
                    'status': tk.Label(self.menu_frame['master'], textvariable=self.variables['menu']['status'], bg=self.colors['bg']['updating'], relief=tk.SUNKEN)
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
        self.colors['transparent'] = self.widgets['trade']['last_trade']['text']['price'].cget('bg')
        logger.debug('self.colors[\'transparent\']: ' + self.colors['transparent'])

        ## Fonts/Formatting ##
        for header in self.widgets:
            logger.debug('header: ' + header)

            for category in self.widgets[header]:
                logger.debug('category: ' + category)

                if category != 'differential':
                    for element in self.widgets[header][category]:
                        logger.debug('element: ' + element)

                        #if element != 'separator':
                        if header == 'trade':
                            selected_font = self.fonts[header][element]
                            logger.debug('selected_font: ' + str(selected_font))

                            for section in self.widgets[header][category][element]:
                                self.widgets[header][category][element][section].config(font=selected_font)

                        elif header == 'analysis':
                            if category == 'titles':
                                selected_font = self.fonts[header][category]
                                logger.debug('selected_font: ' + str(selected_font))

                                self.widgets[header][category][element].config(font=selected_font)

                            else:
                                for section in self.widgets[header][category][element]:
                                    logger.debug('section: ' + section)

                                    selected_font = self.fonts[header][section]
                                    logger.debug('selected_font: ' + str(selected_font))

                                    for label in self.widgets[header][category][element][section]:
                                        logger.debug('label: ' + label)

                                        if element == 'difference' and section == 'variables':
                                                for data_type in self.widgets[header][category][element][section][label]:
                                                    logger.debug('data_type: ' + data_type)

                                                    self.widgets[header][category][element][section][label][data_type].config(font=selected_font)

                                        else:
                                            self.widgets[header][category][element][section][label].config(font=selected_font)

                        else:
                            logger.debug('No font formatting implemented for ' + header + '.')

        #### Create Grid Layout ####

        ## Trade Frames ##
        self.trade_frame['master'].grid(row=0, column=0, rowspan=2, padx=5, pady=1, sticky=tk.E)

        self.trade_frame['active_market'].grid(row=0, column=0, padx=2, pady=10)#, sticky=tk.N)
        self.trade_frame['last_trade'].grid(row=1, column=0, padx=2, pady=10)
        self.trade_frame['orderbook']['main'].grid(row=2, column=0, padx=2, pady=10)
        self.trade_frame['differential'].grid(row=3, column=0, padx=2, pady=10)#, sticky=tk.W+tk.E)

        self.trade_frame['orderbook']['asks'].grid(row=0, column=0, padx=2, sticky=tk.SW+tk.SE)
        self.trade_frame['orderbook']['bids'].grid(row=1, column=0, padx=2, sticky=tk.SW+tk.SE)

        ## Analysis Frames ##

        # Analysis Master Frame
        self.analysis_frame['master'].grid(row=0, column=1, padx=5, pady=1)

        # Analysis Subframes
        self.analysis_frame['buys']['main'].grid(row=1, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['sells']['main'].grid(row=1, column=1, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['all']['main'].grid(row=1, column=2, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)

        self.analysis_frame['buys']['current'].grid(row=0, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['buys']['last'].grid(row=1, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['buys']['difference'].grid(row=2, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)

        self.analysis_frame['sells']['current'].grid(row=0, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['sells']['last'].grid(row=1, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['sells']['difference'].grid(row=2, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)

        self.analysis_frame['all']['current'].grid(row=0, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['all']['last'].grid(row=1, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)
        self.analysis_frame['all']['difference'].grid(row=2, column=0, padx=2, pady=1)#, sticky=tk.N+tk.S+tk.E+tk.W)

        ## Menu Frames ##

        # Menu Master Frame
        self.menu_frame['master'].grid(row=1, column=0, columnspan=2, padx=2, pady=5, sticky=tk.E)

        # Menu Combobox Subframes
        self.menu_frame['exchange'].grid(row=0, column=1, padx=2, pady=1)
        self.menu_frame['market'].grid(row=0, column=2, padx=2, pady=1)
        self.menu_frame['interval'].grid(row=0, column=3, padx=2, pady=1)

        ### Widgets ###

        ## Trade Widgets ##

        # Active Market Title Widgets
        self.widgets['trade']['active_market']['titles']['exchange_market'].grid(row=0, column=0, padx=2, pady=1)
        self.widgets['trade']['active_market']['text']['interval'].grid(row=1, column=0, padx=2, pady=1)

        # Last Trade Text Widgets
        self.widgets['trade']['last_trade']['text']['price'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['trade']['last_trade']['text']['quantity'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['trade']['last_trade']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)

        # Last Trade Variable Widgets
        self.widgets['trade']['last_trade']['variables']['price'].grid(row=0, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['trade']['last_trade']['variables']['quantity'].grid(row=1, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['trade']['last_trade']['variables']['amount'].grid(row=2, column=1, sticky=tk.W, padx=2, pady=1)

        # Orderbook Trade Variable Widgets
        self.widgets['trade']['orderbook']['variables']['asks'].grid(row=0, column=0, sticky=tk.SW+tk.SE)
        self.widgets['trade']['orderbook']['variables']['bids'].grid(row=1, column=0, sticky=tk.NW+tk.NE)

        # Differential Widgets
        self.widgets['trade']['differential']['progressbar'].grid(row=0, column=0, padx=5, pady=2)
        self.widgets['trade']['differential']['text']['value'].grid(row=1, column=0)
        self.widgets['trade']['differential']['text']['change'].grid(row=2, column=0)

        ## Analysis Widgets ##

        # Analysis Master Widgets
        self.widgets['analysis']['titles']['main'].grid(row=0, columnspan=3, padx=2, pady=5)

        # Analysis Category Widgets
        self.widgets['analysis']['buys']['current']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['volume'].grid(row=0, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['price'].grid(row=1, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['amount'].grid(row=2, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['count'].grid(row=3, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['rate_volume'].grid(row=4, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['rate_amount'].grid(row=5, column=0, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['text']['rate_count'].grid(row=6, column=0, sticky=tk.E, padx=2, pady=1)

        # Analysis Variable Widgets
        self.widgets['analysis']['buys']['current']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['current']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['last']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['volume']['absolute'].grid(row=0, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['volume']['percent'].grid(row=0, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['price']['absolute'].grid(row=1, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['price']['percent'].grid(row=1, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['amount']['absolute'].grid(row=2, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['amount']['percent'].grid(row=2, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['count']['absolute'].grid(row=3, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['count']['percent'].grid(row=3, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_volume']['absolute'].grid(row=4, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_volume']['percent'].grid(row=4, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_amount']['absolute'].grid(row=5, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_amount']['percent'].grid(row=5, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_count']['absolute'].grid(row=6, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['buys']['difference']['variables']['rate_count']['percent'].grid(row=6, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['current']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['last']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['volume']['absolute'].grid(row=0, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['volume']['percent'].grid(row=0, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['price']['absolute'].grid(row=1, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['price']['percent'].grid(row=1, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['amount']['absolute'].grid(row=2, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['amount']['percent'].grid(row=2, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['count']['absolute'].grid(row=3, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['count']['percent'].grid(row=3, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_volume']['absolute'].grid(row=4, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_volume']['percent'].grid(row=4, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_amount']['absolute'].grid(row=5, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_amount']['percent'].grid(row=5, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_count']['absolute'].grid(row=6, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['sells']['difference']['variables']['rate_count']['percent'].grid(row=6, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['current']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['volume'].grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['price'].grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['amount'].grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['count'].grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['rate_volume'].grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['rate_amount'].grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['last']['variables']['rate_count'].grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['volume']['absolute'].grid(row=0, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['volume']['percent'].grid(row=0, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['price']['absolute'].grid(row=1, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['price']['percent'].grid(row=1, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['amount']['absolute'].grid(row=2, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['amount']['percent'].grid(row=2, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['count']['absolute'].grid(row=3, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['count']['percent'].grid(row=3, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_volume']['absolute'].grid(row=4, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_volume']['percent'].grid(row=4, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_amount']['absolute'].grid(row=5, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_amount']['percent'].grid(row=5, column=2, sticky=tk.E, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_count']['absolute'].grid(row=6, column=1, sticky=tk.W, padx=2, pady=1)
        self.widgets['analysis']['all']['difference']['variables']['rate_count']['percent'].grid(row=6, column=2, sticky=tk.E, padx=2, pady=1)

        # Menu Widgets
        self.widgets['menu']['variables']['status'].grid(row=0, column=0, ipadx=10, ipady=5, sticky=tk.SW, padx=30, pady=1)

        self.widgets['menu']['comboboxes']['exchange'].grid(row=0, column=0, padx=2, pady=1)
        self.widgets['menu']['comboboxes']['market'].grid(row=0, column=0, padx=2, pady=1)
        self.widgets['menu']['comboboxes']['interval'].grid(row=0, column=0, padx=2, pady=1)

        self.widgets['menu']['buttons']['quit'].grid(row=0, column=4, sticky=tk.SE, padx=30, pady=1)

    def combobox_trace(self, *args):
        """
        *args:
        ('PY_VAR94', '', 'w') --> Exchange Combobox
        ('PY_VAR95', '', 'w') --> Market Combobox
        ('PY_VAR96', '', 'w') --> Interval Combobox
        """

        logger.debug('args: ' + str(args))

        logger.debug('Updating available analysis variables.')

        if args[0] != 'PY_VAR96':
            update_dcm = True
        else:
            update_dcm = False
        logger.debug('update_dcm: ' + str(update_dcm))
        
        process_combobox_result = self.process_combobox_selections(update_depthcache_manager=update_dcm)
        logger.debug('process_combobox_result: ' + str(process_combobox_result))

        if process_combobox_result['success'] == True:
            logger.debug('Updating analysis display.')

            update_analysis_result = self.update_analysis_values()

            if update_analysis_result['success'] == True:
                logger.debug('Updating background colors.')

                if self.gui_data_ready == True:
                    update_background_result = self.update_background_colors()

                    if update_background_result['success'] == False:
                        logger.error('Error while updating analysis display background colors.')

                else:
                    logger.info('GUI data not ready. Skipping background color update.')

            else:
                logger.error('Error while updating analysis display.')

        else:
            logger.error('Error while updating available analysis variables after combobox selection.')

    def orderbook_trace(self, *args):
        #self.widgets['trade']['orderbook']['variables']['asks'].config(bg=self.colors['bg']['orderbook']['asks'])
        #self.widgets['trade']['orderbook']['variables']['bids'].config(bg=self.colors['bg']['orderbook']['bids'])
        pass

    def process_combobox_selections(self, update_depthcache_manager=False):
        process_combobox_return = {'success': True}

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
            elif self.variables['menu']['market'].get() not in self.combobox_markets:
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

            # Set Trade Frame Titles
            active_market_main = self.variables['menu']['exchange'].get() + ' - ' + self.variables['menu']['market'].get()
            logger.debug('active_market_main: ' + active_market_main)

            self.variables['trade']['active_market']['exchange_market'].set(active_market_main)

            interval_display_variable = self.variables['menu']['interval'].get()
            if interval_display_variable[-1] == 's':
                interval_display_variable = interval_display_variable[:-1]
            logger.debug('interval_display_variable: ' + interval_display_variable)

            active_market_interval = interval_display_variable + ' Analysis Interval'
            logger.debug('active_market_interval: ' + active_market_interval)

            self.variables['trade']['active_market']['interval'].set(active_market_interval)

            if update_depthcache_manager == True:
                logger.debug('Updating depth cache manager.')

                # Orderbook
                if self.binance_dcm != None:# and self.binance_dcm.symbol != self.variables['menu']['market'].get():
                    logger.info('New market selected. Closing existing depth cache manager.')
                    self.binance_dcm.close()

                    logger.debug('Opening new depth cache manager.')
                    self.binance_dcm = DepthCacheManager(binance_client, symbol=self.variables['menu']['market'].get(), callback=self.orderbook_handler, refresh_interval=300)

        except Exception as e:
            logger.exception(e)

            process_combobox_return['success'] = False

        finally:
            return process_combobox_return

    def orderbook_handler(self, depth_cache):
        if depth_cache != None:
            asks = depth_cache.get_asks()[:5]
            bids = depth_cache.get_bids()[:5]

            ask_book = ''
            for x in range((len(asks) - 1), -1, -1):
                ask_book += "{:.8f}".format(asks[x][0]) + '      ' + "{:.2f}".format(asks[x][1]) + '\n'
            ask_book = ask_book.rstrip('\n')

            bid_book = ''
            for x in range(0, len(bids)):
                bid_book += "{:.8f}".format(bids[x][0]) + '      ' + "{:.2f}".format(bids[x][1]) + '\n'
            bid_book = bid_book.rstrip('\n')

            if self.variables['trade']['orderbook']['asks'].get() == 'Updating':
                self.widgets['trade']['orderbook']['variables']['asks'].config(bg=self.colors['bg']['orderbook']['asks'])#, justify=tk.LEFT)
                self.trade_frame['orderbook']['asks'].config(bg=self.colors['bg']['orderbook']['asks'])#, justify=tk.LEFT)
            if self.variables['trade']['orderbook']['bids'].get() == 'Updating':
                self.widgets['trade']['orderbook']['variables']['bids'].config(bg=self.colors['bg']['orderbook']['bids'])#, justify=tk.LEFT)
                self.trade_frame['orderbook']['bids'].config(bg=self.colors['bg']['orderbook']['bids'])

            self.variables['trade']['orderbook']['asks'].set(ask_book)
            self.variables['trade']['orderbook']['bids'].set(bid_book)

        else:
            # depth cache had an error and needs to be restarted
            logger.error('Error while retrieving market depth cache.')

    def stop_display(self):
        self.display_active = False
        #self.root.quit()
        #self.root.update()
        #self.root.destroy()

    def run(self):
        self.display_active = True
        logger.debug('self.display_active: ' + str(self.display_active))

        logger.debug('Entering threading run loop.')

        #analysis_check_last = time.time()
        analysis_check_last = 0

        while self.display_active == True:
            try:
                #logger.debug('self.display_active: ' + str(self.display_active))

                ## Update Trade Display Values ##
                #logger.debug('Updating trade display.')

                update_trade_result = self.update_trade_values()

                if update_trade_result['success'] == False:
                    logger.error('Error while updating trade display.')

                ## Update Analysis Display Values ##
                #logger.debug('Updating analysis display.')

                if (time.time() - analysis_check_last) > self.analysis_update_interval:
                    update_analysis_result = self.update_analysis_values()

                    if update_analysis_result['success'] == False:
                        logger.error('Error while updating analysis display.')

                    update_background_result = self.update_background_colors()

                    if update_background_result['success'] == False:
                        logger.error('Error while updating analysis display background colors.')

                    analysis_check_last = time.time()


                if self.gui_data_ready == False:
                    if self.trade_data_ready == True and self.analysis_data_ready == True:
                        self.variables['menu']['status'].set('Ready')
                        self.widgets['menu']['variables']['status'].configure(bg=self.colors['bg']['ready'], relief=tk.RAISED)

                        self.gui_data_ready = True

                        logger.info('GUI data fully updated and ready for use.')

                # Open depth cache manager for orderbook if not yet initialized
                elif self.binance_dcm == None:
                    logger.debug('Initializing depth cache manager.')
                    self.binance_dcm = DepthCacheManager(binance_client, symbol=self.variables['menu']['market'].get(), callback=self.orderbook_handler, refresh_interval=300)

                delay_start = time.time()
                while (time.time() - delay_start) < self.trade_update_interval:
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

        if reactor.running:
            logger.debug('Closing depth cache manager.')
            self.binance_dcm.close()

            logger.info('Stopping reactor.')
            reactor.stop()

        logger.debug('Exited main display loop.')

    def update_trade_values(self):
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
                self.variables['trade']['last_trade']['price'].set("{:.8f}".format(trade_last['price']) + ' ')# + data['quote_currency'] + '/' + data['trade_currency'] + ' ')
                self.variables['trade']['last_trade']['quantity'].set("{:.0f}".format(trade_last['quantity']) + ' ' + trade_last['trade_currency'])
                self.variables['trade']['last_trade']['amount'].set("{:.8f}".format(trade_last['price'] * trade_last['quantity']) + ' ' + trade_last['quote_currency'])
                if trade_last['side'] == 'buy':
                    self.widgets['trade']['last_trade']['variables']['price'].config(image=self.images['trade']['arrow_buy'])
                else:
                    self.widgets['trade']['last_trade']['variables']['price'].config(image=self.images['trade']['arrow_sell'])

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

    def update_analysis_values(self):
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
            analysis_pipeline.append(match_pipeline)

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

                #### Update Analysis Display Values ####

                ## Buys ##
                # Current
                self.variables['analysis']['buys']['current']['volume'].set("{:.2f}".format(analysis_last['current']['volume']['buy']))
                self.variables['analysis']['buys']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['buy']))
                self.variables['analysis']['buys']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['buy']))
                self.variables['analysis']['buys']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['buy']))
                self.variables['analysis']['buys']['current']['rate_volume'].set("{:.4f}".format(analysis_last['current']['rate_volume']['buy']))
                self.variables['analysis']['buys']['current']['rate_amount'].set("{:.4f}".format(analysis_last['current']['rate_amount']['buy']))
                self.variables['analysis']['buys']['current']['rate_count'].set("{:.4f}".format(analysis_last['current']['rate_count']['buy']))

                # Last
                self.variables['analysis']['buys']['last']['volume'].set("{:.2f}".format(analysis_last['last']['volume']['buy']))
                self.variables['analysis']['buys']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['buy']))
                self.variables['analysis']['buys']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['buy']))
                self.variables['analysis']['buys']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['buy']))
                self.variables['analysis']['buys']['last']['rate_volume'].set("{:.4f}".format(analysis_last['last']['rate_volume']['buy']))
                self.variables['analysis']['buys']['last']['rate_amount'].set("{:.4f}".format(analysis_last['last']['rate_amount']['buy']))
                self.variables['analysis']['buys']['last']['rate_count'].set("{:.4f}".format(analysis_last['last']['rate_count']['buy']))

                # Difference
                buy_diff_vol_abs = "{:.0f}".format(analysis_last['difference']['volume']['buy']['absolute'])
                #logger.debug('buy_diff_vol_abs: ' + buy_diff_vol_abs)
                buy_diff_vol_per = "{:+.2%}".format(analysis_last['difference']['volume']['buy']['percent'])
                #logger.debug('buy_diff_vol_per: ' + buy_diff_vol_per)
                buy_diff_price_abs = "{:.8f}".format(analysis_last['difference']['price']['buy']['absolute'])
                #logger.debug('buy_diff_price_abs: ' + buy_diff_price_abs)
                buy_diff_price_per = "{:+.2%}".format(analysis_last['difference']['price']['buy']['percent'])
                #logger.debug('buy_diff_price_per: ' + buy_diff_price_per)
                buy_diff_amt_abs = "{:.2f}".format(analysis_last['difference']['amount']['buy']['absolute'])
                #logger.debug('buy_diff_amt_abs: ' + buy_diff_amt_abs)
                buy_diff_amt_per = "{:+.2%}".format(analysis_last['difference']['amount']['buy']['percent'])
                #logger.debug('buy_diff_amt_per: ' + buy_diff_amt_per)
                buy_diff_count_abs = "{:.0f}".format(analysis_last['difference']['count']['buy']['absolute'])
                #logger.debug('buy_diff_count_abs: ' + buy_diff_count_abs)
                buy_diff_count_per = "{:+.2%}".format(analysis_last['difference']['count']['buy']['percent'])
                #logger.debug('buy_diff_count_per: ' + buy_diff_count_per)
                buy_diff_ratevol_abs = "{:.4f}".format(analysis_last['difference']['rate_volume']['buy']['absolute'])
                #logger.debug('buy_diff_ratevol_abs: ' + buy_diff_ratevol_abs)
                buy_diff_ratevol_per = "{:+.2%}".format(analysis_last['difference']['rate_volume']['buy']['percent'])
                #logger.debug('buy_diff_ratevol_per: ' + buy_diff_ratevol_per)
                buy_diff_rateamt_abs = "{:.4f}".format(analysis_last['difference']['rate_amount']['buy']['absolute'])
                #logger.debug('buy_diff_rateamt_abs: ' + buy_diff_rateamt_abs)
                buy_diff_rateamt_per = "{:+.2%}".format(analysis_last['difference']['rate_amount']['buy']['percent'])
                #logger.debug('buy_diff_rateamt_per: ' + buy_diff_rateamt_per)
                buy_diff_ratecount_abs = "{:.4f}".format(analysis_last['difference']['rate_count']['buy']['absolute'])
                #logger.debug('buy_diff_ratecount_abs: ' + buy_diff_ratecount_abs)
                buy_diff_ratecount_per = "{:+.2%}".format(analysis_last['difference']['rate_count']['buy']['percent'])
                #logger.debug('buy_diff_ratecount_per: ' + buy_diff_ratecount_per)

                self.variables['analysis']['buys']['difference']['volume']['absolute'].set(buy_diff_vol_abs)
                self.variables['analysis']['buys']['difference']['volume']['percent'].set(buy_diff_vol_per)
                self.variables['analysis']['buys']['difference']['price']['absolute'].set(buy_diff_price_abs)
                self.variables['analysis']['buys']['difference']['price']['percent'].set(buy_diff_price_per)
                self.variables['analysis']['buys']['difference']['amount']['absolute'].set(buy_diff_amt_abs)
                self.variables['analysis']['buys']['difference']['amount']['percent'].set(buy_diff_amt_per)
                self.variables['analysis']['buys']['difference']['count']['absolute'].set(buy_diff_count_abs)
                self.variables['analysis']['buys']['difference']['count']['percent'].set(buy_diff_count_per)
                self.variables['analysis']['buys']['difference']['rate_volume']['absolute'].set(buy_diff_ratevol_abs)
                self.variables['analysis']['buys']['difference']['rate_volume']['percent'].set(buy_diff_ratevol_per)
                self.variables['analysis']['buys']['difference']['rate_amount']['absolute'].set(buy_diff_rateamt_abs)
                self.variables['analysis']['buys']['difference']['rate_amount']['percent'].set(buy_diff_rateamt_per)
                self.variables['analysis']['buys']['difference']['rate_count']['absolute'].set(buy_diff_ratecount_abs)
                self.variables['analysis']['buys']['difference']['rate_count']['percent'].set(buy_diff_ratecount_per)

                ## Sells ##
                # Current
                self.variables['analysis']['sells']['current']['volume'].set("{:.2f}".format(analysis_last['current']['volume']['sell']))
                self.variables['analysis']['sells']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['sell']))
                self.variables['analysis']['sells']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['sell']))
                self.variables['analysis']['sells']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['sell']))
                self.variables['analysis']['sells']['current']['rate_volume'].set("{:.4f}".format(analysis_last['current']['rate_volume']['sell']))
                self.variables['analysis']['sells']['current']['rate_amount'].set("{:.4f}".format(analysis_last['current']['rate_amount']['sell']))
                self.variables['analysis']['sells']['current']['rate_count'].set("{:.4f}".format(analysis_last['current']['rate_count']['sell']))

                # Last
                self.variables['analysis']['sells']['last']['volume'].set("{:.2f}".format(analysis_last['last']['volume']['sell']))
                self.variables['analysis']['sells']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['sell']))
                self.variables['analysis']['sells']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['sell']))
                self.variables['analysis']['sells']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['sell']))
                self.variables['analysis']['sells']['last']['rate_volume'].set("{:.4f}".format(analysis_last['last']['rate_volume']['sell']))
                self.variables['analysis']['sells']['last']['rate_amount'].set("{:.4f}".format(analysis_last['last']['rate_amount']['sell']))
                self.variables['analysis']['sells']['last']['rate_count'].set("{:.4f}".format(analysis_last['last']['rate_count']['sell']))

                # Difference
                sell_diff_vol_abs = "{:.0f}".format(analysis_last['difference']['volume']['sell']['absolute'])
                #logger.debug('sell_diff_vol_abs: ' + sell_diff_vol_abs)
                sell_diff_vol_per = "{:+.2%}".format(analysis_last['difference']['volume']['sell']['percent'])
                #logger.debug('sell_diff_vol_per: ' + sell_diff_vol_per)
                sell_diff_price_abs = "{:.8f}".format(analysis_last['difference']['price']['sell']['absolute'])
                #logger.debug('sell_diff_price_abs: ' + sell_diff_price_abs)
                sell_diff_price_per = "{:+.2%}".format(analysis_last['difference']['price']['sell']['percent'])
                #logger.debug('sell_diff_price_per: ' + sell_diff_price_per)
                sell_diff_amt_abs = "{:.2f}".format(analysis_last['difference']['amount']['sell']['absolute'])
                #logger.debug('sell_diff_amt_abs: ' + sell_diff_amt_abs)
                sell_diff_amt_per = "{:+.2%}".format(analysis_last['difference']['amount']['sell']['percent'])
                #logger.debug('sell_diff_amt_per: ' + sell_diff_amt_per)
                sell_diff_count_abs = "{:.0f}".format(analysis_last['difference']['count']['sell']['absolute'])
                #logger.debug('sell_diff_count_abs: ' + sell_diff_count_abs)
                sell_diff_count_per = "{:+.2%}".format(analysis_last['difference']['count']['sell']['percent'])
                #logger.debug('sell_diff_count_per: ' + sell_diff_count_per)
                sell_diff_ratevol_abs = "{:.4f}".format(analysis_last['difference']['rate_volume']['sell']['absolute'])
                #logger.debug('sell_diff_ratevol_abs: ' + sell_diff_ratevol_abs)
                sell_diff_ratevol_per = "{:+.2%}".format(analysis_last['difference']['rate_volume']['sell']['percent'])
                #logger.debug('sell_diff_ratevol_per: ' + sell_diff_ratevol_per)
                sell_diff_rateamt_abs = "{:.4f}".format(analysis_last['difference']['rate_amount']['sell']['absolute'])
                #logger.debug('sell_diff_rateamt_abs: ' + sell_diff_rateamt_abs)
                sell_diff_rateamt_per = "{:+.2%}".format(analysis_last['difference']['rate_amount']['sell']['percent'])
                #logger.debug('sell_diff_rateamt_per: ' + sell_diff_rateamt_per)
                sell_diff_ratecount_abs = "{:.4f}".format(analysis_last['difference']['rate_count']['sell']['absolute'])
                #logger.debug('sell_diff_ratecount_abs: ' + sell_diff_ratecount_abs)
                sell_diff_ratecount_per = "{:+.2%}".format(analysis_last['difference']['rate_count']['sell']['percent'])
                #logger.debug('sell_diff_ratecount_per: ' + sell_diff_ratecount_per)

                self.variables['analysis']['sells']['difference']['volume']['absolute'].set(sell_diff_vol_abs)
                self.variables['analysis']['sells']['difference']['volume']['percent'].set(sell_diff_vol_per)
                self.variables['analysis']['sells']['difference']['price']['absolute'].set(sell_diff_price_abs)
                self.variables['analysis']['sells']['difference']['price']['percent'].set(sell_diff_price_per)
                self.variables['analysis']['sells']['difference']['amount']['absolute'].set(sell_diff_amt_abs)
                self.variables['analysis']['sells']['difference']['amount']['percent'].set(sell_diff_amt_per)
                self.variables['analysis']['sells']['difference']['count']['absolute'].set(sell_diff_count_abs)
                self.variables['analysis']['sells']['difference']['count']['percent'].set(sell_diff_count_per)
                self.variables['analysis']['sells']['difference']['rate_volume']['absolute'].set(sell_diff_ratevol_abs)
                self.variables['analysis']['sells']['difference']['rate_volume']['percent'].set(sell_diff_ratevol_per)
                self.variables['analysis']['sells']['difference']['rate_amount']['absolute'].set(sell_diff_rateamt_abs)
                self.variables['analysis']['sells']['difference']['rate_amount']['percent'].set(sell_diff_rateamt_per)
                self.variables['analysis']['sells']['difference']['rate_count']['absolute'].set(sell_diff_ratecount_abs)
                self.variables['analysis']['sells']['difference']['rate_count']['percent'].set(sell_diff_ratecount_per)

                ## All ##
                # Current
                self.variables['analysis']['all']['current']['volume'].set("{:.2f}".format(analysis_last['current']['volume']['all']))
                self.variables['analysis']['all']['current']['price'].set("{:.8f}".format(analysis_last['current']['price']['all']))
                self.variables['analysis']['all']['current']['amount'].set("{:.2f}".format(analysis_last['current']['amount']['all']))
                self.variables['analysis']['all']['current']['count'].set("{:.0f}".format(analysis_last['current']['count']['all']))
                self.variables['analysis']['all']['current']['rate_volume'].set("{:.4f}".format(analysis_last['current']['rate_volume']['all']))
                self.variables['analysis']['all']['current']['rate_amount'].set("{:.4f}".format(analysis_last['current']['rate_amount']['all']))
                self.variables['analysis']['all']['current']['rate_count'].set("{:.4f}".format(analysis_last['current']['rate_count']['all']))

                # Last
                self.variables['analysis']['all']['last']['volume'].set("{:.2f}".format(analysis_last['last']['volume']['all']))
                self.variables['analysis']['all']['last']['price'].set("{:.8f}".format(analysis_last['last']['price']['all']))
                self.variables['analysis']['all']['last']['amount'].set("{:.2f}".format(analysis_last['last']['amount']['all']))
                self.variables['analysis']['all']['last']['count'].set("{:.0f}".format(analysis_last['last']['count']['all']))
                self.variables['analysis']['all']['last']['rate_volume'].set("{:.4f}".format(analysis_last['last']['rate_volume']['all']))
                self.variables['analysis']['all']['last']['rate_amount'].set("{:.4f}".format(analysis_last['last']['rate_amount']['all']))
                self.variables['analysis']['all']['last']['rate_count'].set("{:.4f}".format(analysis_last['last']['rate_count']['all']))

                # Difference
                all_diff_vol_abs = "{:.0f}".format(analysis_last['difference']['volume']['all']['absolute'])
                #logger.debug('all_diff_vol_abs: ' + all_diff_vol_abs)
                all_diff_vol_per = "{:+.2%}".format(analysis_last['difference']['volume']['all']['percent'])
                #logger.debug('all_diff_vol_per: ' + all_diff_vol_per)
                all_diff_price_abs = "{:.8f}".format(analysis_last['difference']['price']['all']['absolute'])
                #logger.debug('all_diff_price_abs: ' + all_diff_price_abs)
                all_diff_price_per = "{:+.2%}".format(analysis_last['difference']['price']['all']['percent'])
                #logger.debug('all_diff_price_per: ' + all_diff_price_per)
                all_diff_amt_abs = "{:.2f}".format(analysis_last['difference']['amount']['all']['absolute'])
                #logger.debug('all_diff_amt_abs: ' + all_diff_amt_abs)
                all_diff_amt_per = "{:+.2%}".format(analysis_last['difference']['amount']['all']['percent'])
                #logger.debug('all_diff_amt_per: ' + all_diff_amt_per)
                all_diff_count_abs = "{:.0f}".format(analysis_last['difference']['count']['all']['absolute'])
                #logger.debug('all_diff_count_abs: ' + all_diff_count_abs)
                all_diff_count_per = "{:+.2%}".format(analysis_last['difference']['count']['all']['percent'])
                #logger.debug('all_diff_count_per: ' + all_diff_count_per)
                all_diff_ratevol_abs = "{:.4f}".format(analysis_last['difference']['rate_volume']['all']['absolute'])
                #logger.debug('all_diff_ratevol_abs: ' + all_diff_ratevol_abs)
                all_diff_ratevol_per = "{:+.2%}".format(analysis_last['difference']['rate_volume']['all']['percent'])
                #logger.debug('all_diff_ratevol_per: ' + all_diff_ratevol_per)
                all_diff_rateamt_abs = "{:.4f}".format(analysis_last['difference']['rate_amount']['all']['absolute'])
                #logger.debug('all_diff_rateamt_abs: ' + all_diff_rateamt_abs)
                all_diff_rateamt_per = "{:+.2%}".format(analysis_last['difference']['rate_amount']['all']['percent'])
                #logger.debug('all_diff_rateamt_per: ' + all_diff_rateamt_per)
                all_diff_ratecount_abs = "{:.4f}".format(analysis_last['difference']['rate_count']['all']['absolute'])
                #logger.debug('all_diff_ratecount_abs: ' + all_diff_ratecount_abs)
                all_diff_ratecount_per = "{:+.2%}".format(analysis_last['difference']['rate_count']['all']['percent'])
                #logger.debug('all_diff_ratecount_per: ' + all_diff_ratecount_per)

                self.variables['analysis']['all']['difference']['volume']['absolute'].set(all_diff_vol_abs)
                self.variables['analysis']['all']['difference']['volume']['percent'].set(all_diff_vol_per)
                self.variables['analysis']['all']['difference']['price']['absolute'].set(all_diff_price_abs)
                self.variables['analysis']['all']['difference']['price']['percent'].set(all_diff_price_per)
                self.variables['analysis']['all']['difference']['amount']['absolute'].set(all_diff_amt_abs)
                self.variables['analysis']['all']['difference']['amount']['percent'].set(all_diff_amt_per)
                self.variables['analysis']['all']['difference']['count']['absolute'].set(all_diff_count_abs)
                self.variables['analysis']['all']['difference']['count']['percent'].set(all_diff_count_per)
                self.variables['analysis']['all']['difference']['rate_volume']['absolute'].set(all_diff_ratevol_abs)
                self.variables['analysis']['all']['difference']['rate_volume']['percent'].set(all_diff_ratevol_per)
                self.variables['analysis']['all']['difference']['rate_amount']['absolute'].set(all_diff_rateamt_abs)
                self.variables['analysis']['all']['difference']['rate_amount']['percent'].set(all_diff_rateamt_per)
                self.variables['analysis']['all']['difference']['rate_count']['absolute'].set(all_diff_ratecount_abs)
                self.variables['analysis']['all']['difference']['rate_count']['percent'].set(all_diff_ratecount_per)

                # Update Differential Progressbar
                """
                Flow Differential:
                < 50 = Selling dominant
                > 50 = Buying dominant
                """
                #flow_differential = (analysis_last['current']['rate_volume']['buy'] / analysis_last['current']['rate_volume']['all']) * 100
                #sell_flow_differential = analysis_last['current']['rate_volume']['sell'] / analysis_last['current']['rate_volume']['all']
                flow_differential = analysis_last['current']['flow_differential']
                flow_differential_diff_abs = analysis_last['difference']['flow_differential']['absolute']
                flow_differential_diff_per = analysis_last['difference']['flow_differential']['percent']

                self.variables['trade']['differential']['value'].set(round(flow_differential, 2))

                interval_display_variable = self.variables['menu']['interval'].get()
                if interval_display_variable[-1] == 's':
                    interval_display_variable = interval_display_variable[:-1]
                #logger.debug('interval_display_variable: ' + interval_display_variable)

                #self.variables['trade']['differential']['change'].set(
                    #interval_display_variable + ' Change:\n' +
                    #"{:+.2f}".format(flow_differential_diff_abs) +
                    #' (' + "{:+.2%}".format(flow_differential_diff_per) + ')'
                #)
                self.variables['trade']['differential']['change'].set(
                    'Change (' + interval_display_variable + '):\n' +
                    "{:+.2f}".format(flow_differential_diff_abs) +
                    ' (' + "{:+.2%}".format(flow_differential_diff_per) + ')'
                )

                if flow_differential <= 50:
                    differential_current_style = 'red.Horizontal.TProgressbar'
                else:
                    differential_current_style = 'green.Horizontal.TProgressbar'

                self.widgets['trade']['differential']['progressbar'].config(style=differential_current_style)

                self.update_last['analysis'] = datetime.datetime.now()

                logger.info(self.update_last['analysis'].isoformat(timespec='seconds', sep=' ') + ' - Flow Differential: ' + "{:.2f}".format(flow_differential))

                self.root.update_idletasks()

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

    def update_background_colors(self):
        update_background_return = {'success': True}

        try:
            for category in self.widgets['analysis']:
                #logger.debug('category: ' + category)

                if category != 'titles':
                    for section in self.widgets['analysis'][category]['difference']:
                        #logger.debug('section: ' + section)

                        if section == 'variables':
                            for data_type in self.widgets['analysis'][category]['difference'][section]:
                                #logger.debug('data_type: ' + data_type)

                                for element in self.widgets['analysis'][category]['difference'][section][data_type]:
                                    #logger.debug('element: ' + element)

                                    if element == 'percent':
                                        if 'rate' in data_type:
                                            if '-' in self.variables['analysis'][category]['difference'][data_type][element].get():
                                                self.widgets['analysis'][category]['difference'][section][data_type][element].config(bg=self.colors['bg']['negative'])
                                            else:
                                                self.widgets['analysis'][category]['difference'][section][data_type][element].config(bg=self.colors['bg']['positive'])

            self.root.update_idletasks()

        except Exception as e:
            logger.exception(e)

            update_background_return['success'] = False

        finally:
            return update_background_return

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
    display = Display(root)
    display.get_widget_attributes()
    root.mainloop()
    root.destroy()


if __name__ == '__main__':
    main()
