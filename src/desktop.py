"""A native desktop UI; background jobs never access Tk widgets directly."""

import queue
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser

from .analysis import Metadata, UNCLASSIFIED
from .chatgpt_auth import PLAN_SCOPE, delete_profile, load, refresh, session_lock, sign_in, sign_out
from .chatgpt_client import ChatGPTClient
from .desktop_service import (MODES, Cancelled, Topic, approved_mapping, archive_paper,
                              assign, prepare, skip_paper)
from .files import destination
from .scrollable import ScrollableFrame

VERSION = '1.0.2'


class ArchiveApp:
    def __init__(self, root, restore=True):
        self.root = root
        self.root.title(f'Smart Research Archive {VERSION}')
        width = min(1100, max(720, self.root.winfo_screenwidth() - 80))
        height = min(780, max(480, self.root.winfo_screenheight() - 120))
        self.root.geometry(f'{width}x{height}')
        self.root.minsize(720, 480)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.collection = None
        self.ready = False
        self.accounts = []
        self.models = []
        self.controls = []
        self.account_id = None
        self.folder = tk.StringVar(value=str(Path.home() / 'Downloads'))
        self.mode = tk.StringVar(value=MODES[0])
        self.account = tk.StringVar()
        self.model = tk.StringVar()
        self.status = tk.StringVar(value='Ordner auswählen und Analyse starten.')
        self.external = tk.BooleanVar(value=False)
        self.topic_name = tk.StringVar()
        self.topic_included = tk.BooleanVar(value=True)
        self.title, self.author, self.year, self.paper_topic = [tk.StringVar() for _ in range(4)]
        self.target = tk.StringVar(value='Noch keine Datei ausgewählt.')
        self.build()
        for variable in (self.folder, self.mode):
            variable.trace_add('write', lambda *args: self.invalidate())
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)
        if restore:
            try:
                self.restore_accounts(load())
            except Exception:
                self.status.set('Gespeicherte Verbindung konnte nicht gelesen werden. Bitte erneut verbinden.')

    def control(self, widget, state='normal'):
        self.controls.append((widget, state))
        return widget

    def button(self, parent, text, command):
        return self.control(ttk.Button(parent, text=text, command=command))

    def build(self):
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'), foreground='#17395c')
        style.configure('Heading.TLabel', font=('Segoe UI', 14, 'bold'))
        style.configure('Treeview', rowheight=30)
        body = ttk.Frame(self.root, padding=14)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        ttk.Label(body, text='Smart Research Archive', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(body, text='Deine PDFs verstehen, prüfen und geordnet wiederfinden.').grid(row=1, column=0, sticky='w', pady=(3, 8))
        self.tabs = ttk.Notebook(body)
        self.tabs.grid(row=2, column=0, sticky='nsew')
        self.setup, self.topic_page, self.paper_page, self.log_page = [ttk.Frame(self.tabs, padding=10) for _ in range(4)]
        for page, label in zip((self.setup, self.topic_page, self.paper_page, self.log_page),
                               ('1  Ordner & Analyse', '2  Themen prüfen', '3  PDFs bestätigen', 'Verlauf')):
            self.tabs.add(page, text=label)
        self.build_setup()
        self.build_topics()
        self.build_papers()
        self.log = ScrolledText(self.log_page, height=18, wrap='word', font=('Segoe UI', 10), state='disabled')
        self.log.pack(fill='both', expand=True)
        footer = ttk.Frame(body)
        footer.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        status_label = ttk.Label(footer, textvariable=self.status, wraplength=560)
        status_label.grid(row=0, column=0, sticky='ew')
        footer.bind('<Configure>', lambda event: status_label.configure(wraplength=max(200, event.width - 140)))
        self.stop_button = ttk.Button(footer, text='Abbrechen', command=self.stop, state='disabled')
        self.stop_button.grid(row=0, column=1, padx=(10, 0))
        self.progress = ttk.Progressbar(body, mode='indeterminate')
        self.progress.grid(row=4, column=0, sticky='ew', pady=(6, 0))

    def build_setup(self):
        # Reserve the bottom action bar before allocating scrollable form space.
        actions = ttk.Frame(self.setup)
        actions.pack(side='bottom', fill='x', pady=(8, 0))
        self.analyze_button = self.button(actions, 'PDFs analysieren', self.analyze)
        self.analyze_button.pack(side='right')
        self.setup_scroll = ScrollableFrame(self.setup)
        self.setup_scroll.pack(fill='both', expand=True)
        page = self.setup_scroll.content
        ttk.Label(page, text='Welchen Ordner möchtest du sortieren?', style='Heading.TLabel').pack(anchor='w')
        row = ttk.Frame(page)
        row.pack(fill='x', pady=12)
        self.control(ttk.Entry(row, textvariable=self.folder)).pack(side='left', fill='x', expand=True)
        self.button(row, 'Ordner auswählen …', self.choose_folder).pack(side='left', padx=(10, 0))
        ttk.Label(page, text='Nur PDFs direkt in diesem Ordner werden eingelesen. Unterordner bleiben unberührt.\n'
                  'Bestätigte Dateien werden in Themen-Unterordner desselben Ordners verschoben. Bitte Backups behalten.',
                  wraplength=600).pack(anchor='w')
        ttk.Label(page, text='Analyseart', style='Heading.TLabel').pack(anchor='w', pady=(22, 8))
        self.control(ttk.Combobox(page, textvariable=self.mode, values=MODES, state='readonly', width=45),
                     'readonly').pack(anchor='w')
        ttk.Label(page, text='Lokal: nachvollziehbare Keyword-Regeln. ChatGPT: inhaltliche Zusammenfassungen und begründete Themen.',
                  wraplength=600).pack(anchor='w', pady=(8, 16))
        connection = ttk.LabelFrame(page, text='ChatGPT-Verbindung', padding=14)
        connection.pack(fill='x')
        ttk.Label(connection, text='Konto / Workspace').grid(row=0, column=0, sticky='w')
        self.account_box = self.control(ttk.Combobox(connection, textvariable=self.account, state='readonly', width=42), 'readonly')
        self.account_box.grid(row=1, column=0, columnspan=3, sticky='ew', pady=6)
        self.account_box.bind('<<ComboboxSelected>>', self.account_changed)
        self.button(connection, 'Mit ChatGPT verbinden', self.login).grid(row=2, column=0, sticky='w')
        self.button(connection, 'Abmelden', self.logout).grid(row=2, column=1, padx=10)
        ttk.Label(connection, text='Modell').grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.model_box = self.control(ttk.Combobox(connection, textvariable=self.model, state='readonly', width=42), 'readonly')
        self.model_box.grid(row=4, column=0, columnspan=3, sticky='ew', pady=6)
        self.button(connection, 'Modelle laden', self.fetch_models).grid(row=5, column=0, sticky='w')
        ttk.Button(connection, text='Nutzung verwalten', command=lambda: webbrowser.open('https://chatgpt.com/#settings/Usage')).grid(row=5, column=1, padx=10)
        self.delete_connection_button = self.button(connection, 'Verbindung löschen', self.delete_connection)
        self.delete_connection_button.grid(row=6, column=0, sticky='w', pady=(12, 0))
        ttk.Label(connection, text='Abmelden behält den Eintrag. Löschen entfernt die ausgewählte Verbindung aus dieser App.',
                  wraplength=600).grid(row=7, column=0, columnspan=3, sticky='w', pady=(6, 0))
        connection.columnconfigure(0, weight=1)
        self.control(ttk.Checkbutton(page, variable=self.external,
                     text='Externe Verarbeitung mit ChatGPT erlauben')).pack(anchor='w', pady=(16, 5))
        ttk.Label(page, text='Mit diesem Häkchen stimmst du zu, PDF-Texte und Zusammenfassungen an OpenAI zu übermitteln.',
                  wraplength=600).pack(anchor='w', pady=(0, 5))
        ttk.Label(page, text='ChatGPT verwendet deine freigegebenen Abo-Limits. Kein API-Schlüssel und kein automatischer Wechsel zu kostenpflichtiger API-Nutzung.',
                  wraplength=600).pack(anchor='w')

    def build_topics(self):
        row = ttk.Frame(self.topic_page)
        row.pack(side='bottom', fill='x', pady=(8, 0))
        row.columnconfigure(1, weight=1)
        self.classify_button = self.button(row, 'Themen bestätigen & zuordnen', self.classify)
        self.classify_button.grid(row=0, column=0, columnspan=2, sticky='e', pady=(0, 6))
        self.button(row, 'Änderungen übernehmen', self.update_topic).grid(row=1, column=0, sticky='w')
        self.button(row, 'Neues Thema', self.add_topic).grid(row=1, column=1, sticky='w', padx=8)
        self.topics_scroll = ScrollableFrame(self.topic_page)
        self.topics_scroll.pack(fill='both', expand=True)
        page = self.topics_scroll.content
        ttk.Label(page, text='Themen auswählen und anpassen', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(page, text='Bis zu fünf Themen. Die lokale Analyse nutzt Keywords; ChatGPT nutzt die Themenbeschreibung.', wraplength=600).pack(anchor='w', pady=(5, 12))
        self.topic_tree = ttk.Treeview(page, columns=('name', 'included', 'evidence'), show='headings', height=7)
        for column, label, width in (('name', 'Thema', 300), ('included', 'Verwenden', 100), ('evidence', 'Zugehörige PDFs', 500)):
            self.topic_tree.heading(column, text=label)
            self.topic_tree.column(column, width=width)
        self.topic_tree.pack(fill='both', expand=True)
        self.topic_tree.bind('<<TreeviewSelect>>', self.topic_selected)
        row = ttk.Frame(page)
        row.pack(fill='x', pady=12)
        ttk.Label(row, text='Themenname').pack(side='left')
        self.control(ttk.Entry(row, textvariable=self.topic_name, width=42)).pack(side='left', padx=12)
        self.control(ttk.Checkbutton(row, text='Dieses Thema verwenden', variable=self.topic_included)).pack(side='left')
        ttk.Label(page, text='Beschreibung / Keywords (kommagetrennt für lokale Analyse)').pack(anchor='w')
        self.topic_description = self.control(ScrolledText(page, height=4, wrap='word', font=('Segoe UI', 10)))
        self.topic_description.pack(fill='x', pady=6)

    def build_papers(self):
        actions = ttk.Frame(self.paper_page)
        actions.pack(side='bottom', fill='x', pady=(8, 0))
        self.button(actions, 'Überspringen', self.skip).pack(side='left')
        self.accept_button = self.button(actions, 'Bestätigen & einsortieren', self.accept)
        self.accept_button.pack(side='right')
        self.papers_scroll = ScrollableFrame(self.paper_page)
        self.papers_scroll.pack(fill='both', expand=True)
        page = self.papers_scroll.content
        ttk.Label(page, text='Jede Datei bleibt bis zu deiner Bestätigung unverändert.', style='Heading.TLabel', wraplength=700).pack(anchor='w')
        panes = ttk.Panedwindow(page, orient='horizontal')
        panes.pack(fill='both', expand=True, pady=(12, 0))
        left, right = ttk.Frame(panes), ttk.Frame(panes, padding=(16, 0, 0, 0))
        panes.add(left, weight=1)
        panes.add(right, weight=2)
        self.paper_tree = ttk.Treeview(left, columns=('file', 'topic', 'status'), show='headings', selectmode='browse')
        for column, text, width in (('file', 'PDF', 180), ('topic', 'Thema', 120), ('status', 'Status', 100)):
            self.paper_tree.heading(column, text=text)
            self.paper_tree.column(column, width=width)
        bar = ttk.Scrollbar(left, orient='vertical', command=self.paper_tree.yview)
        self.paper_tree.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.paper_tree.pack(fill='both', expand=True)
        self.paper_tree.bind('<<TreeviewSelect>>', self.paper_selected)
        for label, variable in (('Titel', self.title), ('Autor', self.author), ('Jahr', self.year)):
            ttk.Label(right, text=label).pack(anchor='w')
            self.control(ttk.Entry(right, textvariable=variable)).pack(fill='x', pady=(3, 8))
        ttk.Label(right, text='Thema').pack(anchor='w')
        self.paper_topic_box = self.control(ttk.Combobox(right, textvariable=self.paper_topic, state='readonly'), 'readonly')
        self.paper_topic_box.pack(fill='x', pady=(3, 8))
        for variable in (self.title, self.author, self.year, self.paper_topic):
            variable.trace_add('write', lambda *args: self.update_target())
        ttk.Label(right, text='Vorgeschlagener Zielpfad').pack(anchor='w')
        ttk.Label(right, textvariable=self.target, wraplength=530, foreground='#17395c').pack(fill='x', pady=(3, 10))
        ttk.Label(right, text='Begründung, Zusammenfassung und geprüfte Textstellen').pack(anchor='w')
        self.details = ScrolledText(right, height=10, wrap='word', font=('Segoe UI', 10), state='disabled')
        self.details.pack(fill='both', expand=True, pady=6)

    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', str(text) + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def report(self, text):
        self.events.put(('progress', str(text)))

    def start(self, function, completed):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        for widget, _ in self.controls:
            widget.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.progress.start(12)
        def worker():
            try:
                result = function()
                self.events.put(('done', result, completed))
            except Cancelled:
                self.events.put(('cancelled',))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'progress':
                    self.status.set(event[1])
                    self.append_log(event[1])
                    continue
                self.busy = False
                self.progress.stop()
                self.stop_button.configure(state='disabled')
                for widget, state in self.controls:
                    widget.configure(state=state)
                if event[0] == 'done':
                    event[2](event[1])
                elif event[0] == 'cancelled':
                    self.status.set('Abgebrochen. Unbestätigte Dateien bleiben unverändert.')
                else:
                    self.status.set('Vorgang konnte nicht abgeschlossen werden.')
                    self.append_log(event[1])
                    messagebox.showerror('Vorgang nicht abgeschlossen', event[1], parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def choose_folder(self):
        selected = filedialog.askdirectory(title='PDF-Ordner auswählen', parent=self.root)
        if selected:
            self.folder.set(selected)
            self.status.set('Ordner gewählt. Analyse starten, um PDFs einzulesen.')

    def invalidate(self):
        if self.collection is None:
            return
        self.ready = False
        self.collection = None
        self.topic_tree.delete(*self.topic_tree.get_children())
        self.paper_tree.delete(*self.paper_tree.get_children())
        self.target.set('Ordner oder Analyseart geändert. Bitte neu analysieren.')
        self.status.set('Auswahl geändert. Eine neue Analyse ist erforderlich; Dateien bleiben unverändert.')

    def restore_accounts(self, state):
        self.accounts = state['profiles']
        labels = [f'{p["email"]} · Verbindung {i}' for i, p in enumerate(self.accounts, 1)]
        self.account_box.configure(values=['Neues Konto / Workspace', *labels])
        index = next((i for i, p in enumerate(self.accounts) if p['client_id'] == state.get('active')), None)
        self.account.set(labels[index] if index is not None else 'Neues Konto / Workspace')
        self.account_id = self.accounts[index]['client_id'] if index is not None else None

    def account_changed(self, event=None):
        index = self.account_box.current() - 1
        self.account_id = self.accounts[index]['client_id'] if index >= 0 else None
        self.models = []
        self.model.set('')
        self.model_box.configure(values=[])

    def connected(self, result):
        state, models = result
        self.restore_accounts(state)
        self.models = models
        labels = [m['display_name'] + ' · ' + m['slug'] for m in models]
        self.model_box.configure(values=labels)
        self.model.set(labels[0] if labels else '')
        self.status.set('ChatGPT verbunden. Modell auswählen und Analyse starten.')

    def login(self):
        selected = self.account_id
        def job():
            with session_lock():
                state = load()
                previous = next((p for p in state['profiles'] if p['client_id'] == selected), None)
                profile = sign_in(state, previous, ask=lambda _: '', show=self.report,
                                  cancelled=self.cancel.is_set)
                refresh(state, profile)
                return state, ChatGPTClient.list_models(profile)
        self.start(job, self.connected)

    def profile(self, state, selected):
        profile = next((p for p in state['profiles'] if p['client_id'] == selected), None)
        if profile is None or PLAN_SCOPE not in profile.get('scopes', []):
            raise ValueError('Bitte ChatGPT verbinden und die Nutzung deines Abos freigeben.')
        refresh(state, profile)
        return profile

    def fetch_models(self):
        selected = self.account_id
        def job():
            with session_lock():
                state = load()
                return state, ChatGPTClient.list_models(self.profile(state, selected))
        self.start(job, self.connected)

    def logout(self):
        selected = self.account_id
        def job():
            with session_lock():
                state = load()
                profile = next((p for p in state['profiles'] if p['client_id'] == selected), None)
                if profile is None:
                    raise ValueError('Bitte zuerst eine gespeicherte Verbindung auswählen.')
                sign_out(state, profile, show=self.report)
                return state
        def done(state):
            self.restore_accounts(state)
            self.models = []
            self.model.set('')
            self.model_box.configure(values=[])
            self.status.set('Lokal abgemeldet. Details zur Abmeldung stehen im Verlauf.')
        self.start(job, done)

    def model_slug(self):
        index = self.model_box.current()
        return self.models[index]['slug'] if 0 <= index < len(self.models) else None

    def delete_connection(self):
        if self.busy:
            return
        selected = self.account_id
        if not selected:
            messagebox.showinfo('Verbindung auswählen', 'Bitte zuerst eine gespeicherte ChatGPT-Verbindung auswählen.', parent=self.root)
            return
        label = self.account.get()
        if not messagebox.askyesno('Gespeicherte Verbindung löschen?',
                f'{label}\n\nDiesen Eintrag und seine gespeicherten Anmeldedaten aus der App entfernen? '
                'Die App versucht vorher, die Sitzung bei OpenAI zu widerrufen. '
                'Eine verbleibende App-Freigabe kannst du in den ChatGPT-Einstellungen entfernen.\n\n'
                'Deine PDFs und andere gespeicherte Verbindungen bleiben erhalten.',
                parent=self.root, default='no'):
            return
        def job():
            with session_lock():
                state = load()
                revoked = delete_profile(state, selected)
                return state, revoked
        def done(result):
            state, revoked = result
            self.restore_accounts(state)
            self.models = []
            self.model.set('')
            self.model_box.configure(values=[])
            if (self.collection and self.collection.mode == MODES[2]
                    and self.analysis_account == selected):
                self.invalidate()
                self.target.set('ChatGPT-Verbindung gelöscht. Bitte neu verbinden und analysieren.')
            self.status.set('Gespeicherte ChatGPT-Verbindung gelöscht.')
            if revoked is False:
                message = ('Der lokale Eintrag und seine Anmeldedaten wurden gelöscht. '
                           'Der Widerruf bei OpenAI konnte nicht bestätigt werden. '
                           'Bitte trenne die App zusätzlich in den ChatGPT-Einstellungen.')
                messagebox.showwarning('Lokal gelöscht — Widerruf nicht bestätigt', message, parent=self.root)
            else:
                message = ('Der lokale Eintrag und seine Anmeldedaten wurden gelöscht. ' +
                           ('Die gespeicherte Sitzung wurde bei OpenAI widerrufen. ' if revoked else
                            'Für diesen Eintrag war keine erneuerbare Sitzung gespeichert. ') +
                           'Eine verbleibende App-Freigabe kannst du in den ChatGPT-Einstellungen entfernen.')
                messagebox.showinfo('Verbindung gelöscht', message, parent=self.root)
            self.append_log(message)
        self.start(job, done)

    def with_client(self, mode, selected, slug, function):
        if mode != MODES[2]:
            return function(None)
        with session_lock():
            state = load()
            profile = self.profile(state, selected)
            return function(ChatGPTClient(profile, slug, state))

    def analyze(self):
        folder, mode, selected, slug = self.folder.get(), self.mode.get(), self.account_id, self.model_slug()
        if not Path(folder).is_dir():
            messagebox.showerror('Ordner fehlt', 'Bitte einen vorhandenen PDF-Ordner auswählen.', parent=self.root)
            return
        if mode == MODES[2] and (not self.external.get() or not selected or not slug):
            messagebox.showinfo('ChatGPT vorbereiten', 'Bitte Konto und Modell verbinden und der externen Analyse zustimmen.', parent=self.root)
            return
        if self.collection and any(p.status == 'Offen' for p in self.collection.papers):
            if not messagebox.askyesno('Neue Analyse', 'Die bisherige Vorschau verwerfen? Unbestätigte Dateien bleiben unverändert.', parent=self.root):
                return
        self.ready = False
        self.collection = None
        self.paper_tree.delete(*self.paper_tree.get_children())
        self.start(lambda: self.with_client(mode, selected, slug,
                   lambda client: prepare(folder, mode, client, self.report, self.cancel.is_set)), self.prepared)

    def prepared(self, collection):
        self.collection = collection
        self.analysis_account, self.analysis_model = self.account_id, self.model_slug()
        self.topic_tree.delete(*self.topic_tree.get_children())
        for i, topic in enumerate(collection.topics):
            self.topic_tree.insert('', 'end', iid=str(i), values=(topic.name, 'Ja' if topic.included else 'Nein', ', '.join(topic.documents)))
        for error in collection.errors:
            self.append_log(error)
        if collection.topics:
            self.topic_tree.selection_set('0')
        self.status.set(f'{len(collection.papers)} PDFs vorbereitet; {len(collection.errors)} nicht lesbar. Noch keine Datei verschoben.')
        self.tabs.select(self.topic_page)

    def topic_selected(self, event=None):
        selected = self.topic_tree.selection()
        if not selected or self.collection is None:
            return
        topic = self.collection.topics[int(selected[0])]
        self.topic_name.set(topic.name)
        self.topic_included.set(topic.included)
        self.topic_description.delete('1.0', 'end')
        self.topic_description.insert('1.0', topic.description)

    def update_topic(self):
        selected = self.topic_tree.selection()
        if not selected or self.collection is None:
            return
        topic = self.collection.topics[int(selected[0])]
        topic.name = self.topic_name.get().strip()
        topic.description = self.topic_description.get('1.0', 'end').strip()
        topic.included = self.topic_included.get()
        self.topic_tree.item(selected[0], values=(topic.name, 'Ja' if topic.included else 'Nein', ', '.join(topic.documents)))
        self.ready = False
        self.status.set('Thema geändert. Themen erneut bestätigen, bevor Dateien einsortiert werden.')

    def add_topic(self):
        if self.collection is None:
            return
        index = len(self.collection.topics)
        self.collection.topics.append(Topic(f'Neues Thema {index + 1}', '', included=False))
        self.topic_tree.insert('', 'end', iid=str(index), values=(f'Neues Thema {index + 1}', 'Nein', 'Manuell'))
        self.topic_tree.selection_set(str(index))
        self.ready = False

    def classify(self):
        if self.collection is None:
            return
        self.update_topic()
        try:
            topics = approved_mapping(self.collection)
        except ValueError as error:
            messagebox.showerror('Themen prüfen', str(error), parent=self.root)
            return
        if not topics and not messagebox.askyesno('Keine Themen', 'Alle PDFs als Unclassified vorschlagen?', parent=self.root):
            return
        collection = self.collection
        self.start(lambda: self.with_client(collection.mode, self.analysis_account, self.analysis_model,
                   lambda client: assign(collection, topics, client, self.report, self.cancel.is_set)), self.assigned)

    def assigned(self, collection):
        self.ready = True
        self.paper_tree.delete(*self.paper_tree.get_children())
        self.paper_topic_box.configure(values=[*collection.accepted_topics, UNCLASSIFIED])
        for i, paper in enumerate(collection.papers):
            self.paper_tree.insert('', 'end', iid=str(i), values=(paper.source.name, paper.topic, paper.status))
        if collection.papers:
            self.paper_tree.selection_set('0')
        self.status.set('Vorschläge bereit. Jede Datei prüfen und einzeln bestätigen oder überspringen.')
        self.tabs.select(self.paper_page)

    def selected_paper(self):
        selected = self.paper_tree.selection()
        if self.collection is None or not selected:
            return None
        return self.collection.papers[int(selected[0])]

    def paper_selected(self, event=None):
        paper = self.selected_paper()
        if paper is None:
            return
        self.title.set(paper.metadata.title)
        self.author.set(paper.metadata.author)
        self.year.set(paper.metadata.year)
        self.paper_topic.set(paper.topic)
        details = 'Begründung des ursprünglichen Vorschlags:\n' + paper.reason
        if paper.analysis:
            details += '\n\nZusammenfassung:\n' + paper.analysis['summary']
            details += '\n\nIm Text geprüfte Belegstellen:\n' + '\n\n'.join(paper.analysis['evidence'])
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', details)
        self.details.configure(state='disabled')
        self.update_target()

    def current_metadata(self):
        return Metadata(self.title.get().strip(), self.author.get().strip(), self.year.get().strip())

    def update_target(self):
        if not self.ready or self.collection is None:
            return
        paper = self.selected_paper()
        if paper and paper.archived_to:
            self.target.set(str(paper.archived_to))
            return
        try:
            path = destination(self.collection.folder, self.paper_topic.get(), self.current_metadata(), self.collection.accepted_topics)
            self.target.set(str(path))
        except ValueError:
            self.target.set('Bitte ein bestätigtes Thema auswählen.')

    def accept(self):
        paper = self.selected_paper()
        if not self.ready or paper is None or paper.status != 'Offen':
            messagebox.showinfo('Datei prüfen', 'Bitte eine offene Datei aus einer bestätigten Vorschau auswählen.', parent=self.root)
            return
        metadata, topic, collection = self.current_metadata(), self.paper_topic.get(), self.collection
        iid = self.paper_tree.selection()[0]
        def done(target):
            self.paper_tree.item(iid, values=(paper.source.name, paper.topic, paper.status))
            self.append_log(f'Einsortiert: {target}')
            self.status.set('Datei einsortiert. Nächste Datei prüfen.')
            self.next_paper()
        self.start(lambda: archive_paper(collection, paper, metadata, topic), done)

    def skip(self):
        paper = self.selected_paper()
        if not self.ready or paper is None:
            return
        skip_paper(paper)
        self.paper_tree.item(self.paper_tree.selection()[0], values=(paper.source.name, paper.topic, paper.status))
        self.status.set('Übersprungen. Die Originaldatei bleibt an ihrem Ort.')
        self.next_paper()

    def next_paper(self):
        for i, paper in enumerate(self.collection.papers):
            if paper.status == 'Offen':
                self.paper_tree.selection_set(str(i))
                self.paper_tree.see(str(i))
                return
        self.status.set('Prüfung abgeschlossen. Unbestätigte und übersprungene PDFs bleiben im Ausgangsordner.')

    def stop(self):
        self.cancel.set()
        self.status.set('Abbruch angefordert. Eine laufende Anfrage oder Dateikopie wird zunächst beendet.')

    def close(self):
        if self.busy:
            self.stop()
            messagebox.showinfo('Vorgang wird beendet', 'Bitte warten, bis der laufende Vorgang beendet ist. Danach kannst du das Fenster schließen.', parent=self.root)
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    ArchiveApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
