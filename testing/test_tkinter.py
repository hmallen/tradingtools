import tkinter as tk

class Display(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        self.hi_there = tk.Button(self, text='Hello World\n(Click Me)', command=self.say_hi)
        self.hi_there.pack(side='top')

        self.quit = tk.Button(self, text='QUIT', fg='red', command=root.destroy)
        self.quit.pack(side='bottom')

    def say_hi(self):
        print('Hello, world!')

root = tk.Tk()
display = Display(master=root)
display.mainloop()
