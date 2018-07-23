import time
import tkinter as tk

class Display(tk.Frame):
    def __init__(self, master=None):
        self.test_var = 0
        super().__init__(master)
        self.pack()
        self.create_widgets()
        self.main_loop()

    def create_widgets(self):
        # Top
        self.action = tk.Button(self, text='Hello, world!\n(Click Me)', command=self.button_action)
        self.action.pack(side=tk.TOP)

        # Left
        self.label_left = tk.Label(self, text='Label Left!', font=('Helvetica', 16))
        self.label_left.pack(side=tk.LEFT)

        # Right
        self.label_var = tk.Label(self, text=self.test_var, font=('Arial', 16))
        self.label_var.pack(side=tk.RIGHT)

        # Bottom
        self.quit = tk.Button(self, text='Quit', fg='red', command=root.destroy)
        self.quit.pack(side=tk.BOTTOM)

    def button_action(self):
        print('Hello, world!')

    def main_loop(self):
            loop_delay = 5

            while (True):
                try:
                    print('Incrementing test_var +1.')
                    self.test_var += 1
                    self.label_var['text'] = self.test_var
                    self.label_var.pack()
                    self.update()
                    loop_start = time.time()
                    while (time.time() - loop_start) < loop_delay:
                        time.sleep(0.1)

                except KeyboardInterrupt:
                    print('Exit signal received.')
                    break


if __name__ == '__main__':
    test_var = 0
    root = tk.Tk()
    display = Display(master=root)

    """
    loop_delay = 5
    while (True):
        print('Incrementing test_var +1.')
        test_var += 1
        loop_start = time.time()
        while (time.time() - loop_start) < loop_delay:
            time.sleep(0.1)
    """
