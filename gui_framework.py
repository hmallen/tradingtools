import time
import tkinter as tk
import threading

class App(threading.Thread):

    def __init__(self, master=None):
        self.root = master

        threading.Thread.__init__(self)

        self.test_var = tk.IntVar()
        self.test_var.set(0)

        self.create_widgets()

        self.start()

    def create_widgets(self):
        self.label_widget = tk.Label(self.root, textvariable=self.test_var)
        self.label_widget.pack(side=tk.TOP)

        self.quit_button = tk.Button(self.root, text='Quit', command=self.stop_display)
        self.quit_button.pack(side=tk.BOTTOM)

    def stop_display(self):
        self.loop_active = False
        self.root.quit()
        #self.root.update()
        #self.root.destroy()

    def run(self):
        self.loop_active = True

        for x in range(0, 5):
            if self.loop_active == False:
                self.stop_display()
                break
            self.test_var.set(self.test_var.get() + 1)
            time.sleep(1)

        """
        while self.loop_active == True:
            pass
        """


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()
