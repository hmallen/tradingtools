import logging
import os
import sys

import threading
import tkinter as tk

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Display(threading.Thread):

    def __init__(self, master=None, toplevel=None):
        self.root = master
        self.top = toplevel

        threading.Thread.__init__(self)

        self.create_widgets()

        self.start()

    def create_widgets(self):
        self.widgets = {}

        self.widgets['welcome_message'] = tk.

    def run(self):
        pass


if __name__ == '__main__':
    root = tk.Tk()
    top = tk.Toplevel()
    app = Display(master=root, toplevel=top)
    root.mainloop()
    root.destroy()
