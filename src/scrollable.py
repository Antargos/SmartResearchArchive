"""Scrollable page content; primary action buttons stay outside this viewport."""

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vertical = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vertical.grid(row=0, column=1, sticky='ns')
        self.horizontal.grid(row=1, column=0, sticky='ew')
        self.content = ttk.Frame(self.canvas, padding=(0, 0, 8, 8))
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.canvas.bind('<Configure>', self.resize)
        self.content.bind('<Configure>', self.resize)
        # Tk does not bubble wheel events from child widgets to a parent frame.
        # A guarded application binding handles only events inside this viewport.
        for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.bind_all(event, self.wheel, add='+')

    def resize(self, event=None):
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth())
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self.window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def wheel(self, event):
        widget = event.widget
        # Text fields, lists and comboboxes retain their own scrolling behavior.
        if widget.winfo_class() in ('Text', 'Treeview', 'TCombobox'):
            return
        while widget is not None and widget is not self:
            widget = getattr(widget, 'master', None)
        if widget is None:
            return
        delta = getattr(event, 'delta', 0)
        if getattr(event, 'num', None) == 4:
            steps = -1
        elif getattr(event, 'num', None) == 5:
            steps = 1
        elif delta:
            steps = -max(1, abs(int(delta / 120))) if delta > 0 else max(1, abs(int(delta / 120)))
        else:
            return
        scroll = self.canvas.xview_scroll if event.state & 1 else self.canvas.yview_scroll
        scroll(steps, 'units')
        return 'break'
