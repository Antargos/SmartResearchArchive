"""A native desktop UI; background jobs never access Tk widgets directly."""

import queue
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser
import json
import os
from copy import deepcopy
from dataclasses import asdict

from .analysis import Metadata, UNCLASSIFIED
from .chatgpt_auth import PLAN_SCOPE, delete_profile, load, refresh, session_lock, sign_in, sign_out
from .chatgpt_client import ChatGPTClient
from .desktop_service import (MODES, Cancelled, Collection, Topic, approved_mapping, archive_paper,
                              assign, prepare, skip_paper)
from .files import destination
from .scrollable import ScrollableFrame
from .archive_store import ArchiveStore, existing_profile
from .archive_workflow import (STRATEGIES, archive_one, assign_archive, imported_topics,
                               prepare_archive, profile_topics, undo_last)
from .preferences import last_folder, remember_folder
from .semantic import review_topic_fit

VERSION = '2.0.0'


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
        self.audit_next = False
        self.accounts = []
        self.models = []
        self.controls = []
        self.account_id = None
        self.restore_enabled = restore
        self.draft_topics = []
        self.pending_correction_ids = []
        self.saved_profile = None
        self.archive_timer = None
        self.folder = tk.StringVar(value=last_folder() if restore else str(Path.home() / 'Downloads'))
        self.mode = tk.StringVar(value=MODES[0])
        self.engine = tk.StringVar(value='Lokal')
        self.strategy = tk.StringVar(value=STRATEGIES[1])
        self.archive_info = tk.StringVar(value='Neues Archiv: Themen einmalig festlegen oder Vorschläge prüfen.')
        self.topic_keywords = tk.StringVar()
        self.fit_review = tk.StringVar()
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
        self.folder.trace_add('write', self.folder_changed)
        self.engine.trace_add('write', self.options_changed)
        self.strategy.trace_add('write', self.options_changed)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)
        if restore:
            try:
                self.restore_accounts(load())
            except Exception:
                self.status.set('Gespeicherte Verbindung konnte nicht gelesen werden. Bitte erneut verbinden.')
            self.load_archive_profile()
        self.options_changed()

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
                               ('1 Start', '2 Themen', '3 PDFs', 'Verlauf')):
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
        ttk.Label(page, text='1. Wie möchtest du analysieren?', style='Heading.TLabel').pack(anchor='w')
        self.control(ttk.Combobox(page, textvariable=self.engine, values=('Lokal', 'ChatGPT (LLM)'),
                                  state='readonly', width=40), 'readonly').pack(anchor='w', pady=(8, 12))
        ttk.Label(page, text='2. Woher kommen die Themen?', style='Heading.TLabel').pack(anchor='w')
        self.control(ttk.Combobox(page, textvariable=self.strategy, values=STRATEGIES,
                                  state='readonly', width=40), 'readonly').pack(anchor='w', pady=8)
        self.button(page, 'Themen / Keywords festlegen oder bearbeiten', self.edit_rules).pack(anchor='w', pady=(0, 14))
        ttk.Label(page, text='Welchen Ordner möchtest du sortieren?', style='Heading.TLabel').pack(anchor='w')
        row = ttk.Frame(page)
        row.pack(fill='x', pady=12)
        self.control(ttk.Entry(row, textvariable=self.folder)).pack(side='left', fill='x', expand=True)
        self.button(row, 'Ordner auswählen …', self.choose_folder).pack(side='left', padx=(10, 0))
        ttk.Label(page, text='Nur PDFs direkt in diesem Ordner werden eingelesen. Unterordner bleiben unberührt.\n'
                  'Bestätigte Dateien werden in Themen-Unterordner desselben Ordners verschoben. Bitte Backups behalten.',
                  wraplength=600).pack(anchor='w')
        ttk.Label(page, textvariable=self.archive_info, wraplength=600, foreground='#17395c').pack(anchor='w', pady=10)
        self.button(page, 'Letzte Einsortierung rückgängig machen', self.undo).pack(anchor='w', pady=4)
        self.button(page, 'Bestehende Sammlung ausdrücklich neu prüfen', self.audit_archive).pack(anchor='w', pady=4)
        self.button(page, 'Analysecache leeren', self.clear_cache).pack(anchor='w', pady=4)
        self.llm_panel = ttk.Frame(page)
        connection = ttk.LabelFrame(self.llm_panel, text='ChatGPT-Verbindung', padding=14)
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
        self.control(ttk.Checkbutton(self.llm_panel, variable=self.external,
                     text='Externe Verarbeitung mit ChatGPT erlauben')).pack(anchor='w', pady=(16, 5))
        ttk.Label(self.llm_panel, text='Mit diesem Häkchen stimmst du zu, PDF-Texte und Zusammenfassungen an OpenAI zu übermitteln.',
                  wraplength=600).pack(anchor='w', pady=(0, 5))
        ttk.Label(self.llm_panel, text='ChatGPT verwendet deine freigegebenen Abo-Limits. Kein API-Schlüssel und kein automatischer Wechsel zu kostenpflichtiger API-Nutzung.',
                  wraplength=600).pack(anchor='w')

    def build_topics(self):
        row = ttk.Frame(self.topic_page)
        row.pack(side='bottom', fill='x', pady=(8, 0))
        row.columnconfigure(1, weight=1)
        self.classify_button = self.button(row, 'Regeln bestätigen & weiter', self.classify)
        self.classify_button.grid(row=0, column=0, columnspan=2, sticky='e', pady=(0, 6))
        self.button(row, 'Änderungen übernehmen', self.update_topic).grid(row=1, column=0, sticky='w')
        self.button(row, 'Neues Thema', self.add_topic).grid(row=1, column=1, sticky='w', padx=8)
        self.topics_scroll = ScrollableFrame(self.topic_page)
        self.topics_scroll.pack(fill='both', expand=True)
        page = self.topics_scroll.content
        ttk.Label(page, text='Themen auswählen und anpassen', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(page, text='Bis zu fünf Themen. Eigene Regeln bleiben erhalten. Neue Vorschläge werden erst nach deiner Bestätigung gespeichert.', wraplength=600).pack(anchor='w', pady=(5, 12))
        ttk.Label(page, textvariable=self.fit_review, wraplength=700, foreground='#17395c').pack(anchor='w', pady=6)
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
        ttk.Label(page, text='Themenbeschreibung (für die inhaltliche LLM-Zuordnung)').pack(anchor='w')
        self.topic_description = self.control(ScrolledText(page, height=4, wrap='word', font=('Segoe UI', 10)))
        self.topic_description.pack(fill='x', pady=6)
        ttk.Label(page, text='Keywords (kommagetrennt; für lokale Sortierung erforderlich)').pack(anchor='w')
        self.control(ttk.Entry(page, textvariable=self.topic_keywords)).pack(fill='x', pady=6)

    def build_papers(self):
        actions = ttk.Frame(self.paper_page)
        actions.pack(side='bottom', fill='x', pady=(8, 0))
        self.button(actions, 'Überspringen', self.skip).pack(side='left')
        self.accept_button = self.button(actions, 'Bestätigen & einsortieren', self.accept)
        self.accept_button.pack(side='right')
        more = ttk.Frame(self.paper_page)
        more.pack(side='bottom', fill='x', pady=(6, 0))
        self.button(more, 'PDF öffnen', self.open_pdf).pack(side='left')
        self.button(more, 'Später prüfen', self.defer).pack(side='left', padx=6)
        self.button(more, 'Erneut prüfen', self.reopen).pack(side='left')
        self.papers_scroll = ScrollableFrame(self.paper_page)
        self.papers_scroll.pack(fill='both', expand=True)
        page = self.papers_scroll.content
        self.button(page, 'Neue Themen vorschlagen / Regeln prüfen', self.propose_additions).pack(anchor='w', pady=6)
        self.button(page, 'Regelvorschläge aus Korrekturen', self.correction_rules).pack(anchor='w', pady=6)
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

    def folder_changed(self, *args):
        if self.archive_timer:
            self.root.after_cancel(self.archive_timer)
        self.archive_timer = self.root.after(350, self.load_archive_profile)

    def load_archive_profile(self):
        self.archive_timer = None
        if self.busy:
            return
        try:
            self.saved_profile = existing_profile(self.folder.get()) if Path(self.folder.get()).is_dir() else None
            if self.saved_profile is not None:
                self.draft_topics = profile_topics(self.saved_profile)
                self.engine.set('ChatGPT (LLM)' if self.saved_profile['engine'] == 'llm' else 'Lokal')
                self.strategy.set(STRATEGIES[0])
                self.archive_info.set(f'Archiv erkannt: {len(self.draft_topics)} gespeicherte Themen. Neue PDFs werden mit diesen Regeln einsortiert.')
            else:
                self.draft_topics = []
                state_path = Path(self.folder.get()) / '.smart-research-archive' / 'archive.sqlite3'
                if state_path.is_file():
                    store = ArchiveStore(self.folder.get())
                    self.draft_topics = [Topic(**item) for item in store.get('draft_topics', [])]
                    self.engine.set('ChatGPT (LLM)' if store.get('draft_engine') == 'llm' else 'Lokal')
                if self.strategy.get() == STRATEGIES[0]:
                    self.strategy.set(STRATEGIES[1])
                self.archive_info.set('Noch kein Archivprofil. Themen einmalig festlegen, vorschlagen oder vorhandene Ordner übernehmen.')
                if self.draft_topics:
                    self.archive_info.set('Gespeicherter Themenentwurf gefunden. Du kannst die unterbrochene Vorbereitung fortsetzen.')
            self.render_topics()
        except Exception as error:
            self.saved_profile = None
            self.archive_info.set(f'Archivprofil konnte nicht geladen werden: {error}')

    def options_changed(self, *args):
        mode = MODES[2] if self.engine.get() == 'ChatGPT (LLM)' else MODES[0]
        if self.mode.get() != mode:
            self.mode.set(mode)
        if self.engine.get() == 'ChatGPT (LLM)':
            self.llm_panel.pack(fill='x', pady=(16, 0))
        else:
            self.llm_panel.pack_forget()
        # Showing a panel changes requested content size, even while the canvas
        # keeps the existing frame size. Recalculate after Tk lays out children.
        self.root.after_idle(self.setup_scroll.resize)

    def topic_list(self):
        return self.collection.topics if self.collection else self.draft_topics

    def render_topics(self):
        self.topic_tree.delete(*self.topic_tree.get_children())
        for i, topic in enumerate(self.topic_list()):
            evidence = ', '.join(topic.documents) or topic.note or topic.origin
            self.topic_tree.insert('', 'end', iid=str(i), values=(topic.name, 'Ja' if topic.included else 'Nein', evidence))
        if self.topic_list():
            self.topic_tree.selection_set('0')

    def edit_rules(self):
        if self.archive_timer:
            self.root.after_cancel(self.archive_timer)
            self.load_archive_profile()
        if self.collection:
            self.draft_topics = deepcopy(self.collection.topics)
            self.invalidate()
        if self.strategy.get() == STRATEGIES[3]:
            try:
                self.draft_topics = imported_topics(self.folder.get())
            except OSError as error:
                messagebox.showerror('Ordner prüfen', str(error), parent=self.root)
                return
        elif self.strategy.get() == STRATEGIES[0] and self.saved_profile:
            self.draft_topics = profile_topics(self.saved_profile)
            self.strategy.set(STRATEGIES[1])
        self.fit_review.set('Regeln einmalig festlegen. Das Archiv merkt sich bestätigte Themen und Keywords.')
        self.render_topics()
        self.tabs.select(self.topic_page)

    def validate_draft(self, topics, mode):
        candidate = Collection(Path(self.folder.get()), mode, [], topics, [])
        mapping = approved_mapping(candidate)
        if mode != MODES[2] and any(t.included and not t.keywords for t in topics):
            raise ValueError('Für lokale Themen bitte eigene Keywords eintragen; eine Beschreibung allein reicht nicht.')
        return mapping

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
        preferred = ''
        if self.saved_profile and Path(self.folder.get()).is_dir():
            preferred = ArchiveStore(self.folder.get()).get('preferred_model', '')
        preferred_index = next((i for i, model in enumerate(models) if model['slug'] == preferred), 0)
        self.model.set(labels[preferred_index] if labels else '')
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
        if self.archive_timer:
            self.root.after_cancel(self.archive_timer)
            self.load_archive_profile()
        folder, mode, selected, slug = self.folder.get(), self.mode.get(), self.account_id, self.model_slug()
        strategy = self.strategy.get()
        if not Path(folder).is_dir():
            messagebox.showerror('Ordner fehlt', 'Bitte einen vorhandenen PDF-Ordner auswählen.', parent=self.root)
            return
        if mode == MODES[2] and (not self.external.get() or not selected or not slug):
            messagebox.showinfo('ChatGPT vorbereiten', 'Bitte Konto und Modell verbinden und der externen Analyse zustimmen.', parent=self.root)
            return
        if strategy == STRATEGIES[0]:
            if self.saved_profile is None:
                messagebox.showinfo('Archivregeln fehlen', 'Bitte zuerst Themen festlegen oder Vorschläge prüfen.', parent=self.root)
                return
            topics = profile_topics(self.saved_profile)
        else:
            self.update_topic()
            topics = deepcopy(self.draft_topics if self.collection is None else self.collection.topics)
        if strategy in (STRATEGIES[0], STRATEGIES[1], STRATEGIES[3]):
            try:
                if not topics and strategy != STRATEGIES[0]:
                    self.edit_rules()
                    messagebox.showinfo('Themen festlegen', 'Bitte eigene Themen mit Keywords festlegen und bestätigen.', parent=self.root)
                    return
                self.validate_draft(topics, mode)
            except ValueError as error:
                messagebox.showerror('Themen prüfen', str(error), parent=self.root)
                return
        if self.collection and any(p.status == 'Offen' for p in self.collection.papers):
            if not messagebox.askyesno('Neue Analyse', 'Die bisherige Vorschau verwerfen? Unbestätigte Dateien bleiben unverändert.', parent=self.root):
                return
        self.ready = False
        self.collection = None
        self.analysis_account, self.analysis_model, self.analysis_strategy = selected, slug, strategy
        audit, self.audit_next = self.audit_next, False
        self.paper_tree.delete(*self.paper_tree.get_children())
        if self.restore_enabled:
            remember_folder(folder)
        def job():
            store = ArchiveStore(folder)
            if strategy != STRATEGIES[0]:
                store.set('draft_topics', [asdict(topic) for topic in topics])
                store.set('draft_engine', 'llm' if mode == MODES[2] else 'local')
            return self.with_client(mode, selected, slug, lambda client: prepare_archive(
                folder, mode, strategy, topics, slug or '', client, self.report, self.cancel.is_set, audit))
        self.start(job, self.prepared)

    def prepared(self, collection):
        self.collection = collection
        if not hasattr(self, 'analysis_account'):
            self.analysis_account, self.analysis_model = self.account_id, self.model_slug()
        self.draft_topics = deepcopy(collection.topics)
        self.fit_review.set(collection.topic_review)
        self.render_topics()
        for error in collection.errors:
            self.append_log(error)
        self.status.set(f'{len(collection.papers)} PDFs vorbereitet; {len(collection.errors)} Hinweise im Verlauf. Noch keine Datei verschoben.')
        if getattr(self, 'analysis_strategy', None) == STRATEGIES[0]:
            self.classify(use_saved=True)
            return
        self.tabs.select(self.topic_page)

    def topic_selected(self, event=None):
        selected = self.topic_tree.selection()
        if not selected or not self.topic_list():
            return
        topic = self.topic_list()[int(selected[0])]
        self.topic_name.set(topic.name)
        self.topic_included.set(topic.included)
        self.topic_description.delete('1.0', 'end')
        self.topic_description.insert('1.0', topic.description)
        self.topic_keywords.set(', '.join(topic.keywords))

    def update_topic(self):
        selected = self.topic_tree.selection()
        if not selected or not self.topic_list():
            return
        topic = self.topic_list()[int(selected[0])]
        topic.name = self.topic_name.get().strip()
        topic.description = self.topic_description.get('1.0', 'end').strip() or topic.name
        topic.keywords = tuple(dict.fromkeys(word.strip() for word in self.topic_keywords.get().split(',') if word.strip()))
        topic.included = self.topic_included.get()
        self.topic_tree.item(selected[0], values=(topic.name, 'Ja' if topic.included else 'Nein', ', '.join(topic.documents)))
        self.ready = False
        self.status.set('Thema geändert. Themen erneut bestätigen, bevor Dateien einsortiert werden.')

    def add_topic(self):
        index = len(self.topic_list())
        self.topic_list().append(Topic(f'Neues Thema {index + 1}', '', included=True))
        self.topic_tree.insert('', 'end', iid=str(index), values=(f'Neues Thema {index + 1}', 'Ja', 'Manuell'))
        self.topic_tree.selection_set(str(index))
        self.ready = False

    def classify(self, use_saved=False):
        if self.collection is None:
            self.update_topic()
            self.tabs.select(self.setup)
            self.analyze()
            return
        if not use_saved:
            self.update_topic()
        try:
            topics = self.validate_draft(self.collection.topics, self.collection.mode)
        except ValueError as error:
            messagebox.showerror('Themen prüfen', str(error), parent=self.root)
            return
        if not topics and not messagebox.askyesno('Keine Themen', 'Alle PDFs als Unclassified vorschlagen?', parent=self.root):
            return
        collection = self.collection
        definitions = deepcopy(collection.topics)
        correction_ids = list(self.pending_correction_ids)
        def job():
            store = ArchiveStore(collection.folder)
            store.save_profile(definitions, 'llm' if collection.mode == MODES[2] else 'local')
            store.resolve_corrections(correction_ids)
            store.set('preferred_model', self.analysis_model or '')
            return self.with_client(collection.mode, self.analysis_account, self.analysis_model,
                lambda client: assign_archive(collection, topics, store, self.analysis_model or '',
                                               client, self.report, self.cancel.is_set))
        self.start(job, self.assigned)

    def assigned(self, collection):
        self.ready = True
        self.pending_correction_ids = []
        if self.restore_enabled:
            self.saved_profile = existing_profile(collection.folder)
            self.archive_info.set(f'Archivregeln gespeichert: {len(collection.accepted_topics)} Themen. Beim nächsten Mal direkt wiederverwendbar.')
            self.strategy.set(STRATEGIES[0])
        self.paper_tree.delete(*self.paper_tree.get_children())
        self.paper_topic_box.configure(values=[*collection.accepted_topics, UNCLASSIFIED])
        for i, paper in enumerate(collection.papers):
            self.paper_tree.insert('', 'end', iid=str(i), values=(paper.source.name, paper.topic, paper.status))
        if collection.papers:
            self.next_paper()
        duplicates = sum(p.status == 'Duplikat' for p in collection.papers)
        later = sum(p.status == 'Später prüfen' for p in collection.papers)
        self.status.set(f'Vorschläge bereit. {duplicates} Duplikate, {later} für später vorgemerkt. Jede Verschiebung einzeln bestätigen.')
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
        details += '\n\nHerkunft der Metadaten:\n' + '\n'.join(
            f'{label}: {paper.metadata.sources.get(key, "Nicht dokumentiert")}'
            for key, label in (('author', 'Autor'), ('year', 'Jahr'), ('title', 'Titel')))
        if paper.metadata.warnings:
            details += '\n\nMetadaten-Hinweise:\n' + '\n'.join(paper.metadata.warnings)
        if paper.status == 'Duplikat':
            details += f'\n\nIdentische Datei: {paper.duplicate_of}\nKeine erneute LLM-Analyse und keine automatische Löschung.'
        if paper.analysis:
            details += '\n\nZusammenfassung:\n' + paper.analysis['summary']
            details += '\n\nIm Text geprüfte Belegstellen:\n' + '\n\n'.join(paper.analysis['evidence'])
            if paper.analysis.get('warnings'):
                details += '\n\nHinweise:\n' + '\n'.join(paper.analysis['warnings'])
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', details)
        self.details.configure(state='disabled')
        self.update_target()

    def current_metadata(self):
        metadata = Metadata(self.title.get().strip(), self.author.get().strip(), self.year.get().strip())
        paper = self.selected_paper()
        if paper:
            metadata.sources = dict(paper.metadata.sources)
            for key in ('title', 'author', 'year'):
                if getattr(metadata, key) != getattr(paper.metadata, key):
                    metadata.sources[key] = 'Manuell korrigiert'
        return metadata

    def update_target(self):
        if not self.ready or self.collection is None:
            return
        paper = self.selected_paper()
        if paper and paper.archived_to:
            self.target.set(str(paper.archived_to))
            return
        if paper and paper.status == 'Duplikat':
            self.target.set(f'Duplikat — unverändert belassen. Vorhanden: {paper.duplicate_of}')
            return
        try:
            current = paper.source if paper and self.collection.include_archived else None
            path = destination(self.collection.folder, self.paper_topic.get(), self.current_metadata(),
                               self.collection.accepted_topics, current_file=current)
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
        self.start(lambda: archive_one(collection, paper, metadata, topic, ArchiveStore(collection.folder)), done)

    def skip(self):
        paper = self.selected_paper()
        if not self.ready or paper is None:
            return
        skip_paper(paper)
        if paper.status == 'Übersprungen':
            ArchiveStore(self.collection.folder).save_decision(paper, paper.status)
        self.paper_tree.item(self.paper_tree.selection()[0], values=(paper.source.name, paper.topic, paper.status))
        self.status.set('Übersprungen. Die Originaldatei bleibt an ihrem Ort.')
        self.next_paper()

    def defer(self):
        paper = self.selected_paper()
        if not self.ready or paper is None or paper.status != 'Offen':
            return
        paper.metadata = self.current_metadata()
        paper.topic = self.paper_topic.get()
        paper.status = 'Später prüfen'
        ArchiveStore(self.collection.folder).save_decision(paper, paper.status)
        self.paper_tree.item(self.paper_tree.selection()[0], values=(paper.source.name, paper.topic, paper.status))
        self.next_paper()

    def reopen(self):
        paper = self.selected_paper()
        if paper is None or paper.status not in ('Später prüfen', 'Übersprungen'):
            messagebox.showinfo('Datei auswählen', 'Bitte eine übersprungene oder für später vorgemerkte Datei auswählen.', parent=self.root)
            return
        paper.status = 'Offen'
        store = ArchiveStore(self.collection.folder)
        store.save_decision(paper, 'Offen')
        self.paper_tree.item(self.paper_tree.selection()[0], values=(paper.source.name, paper.topic, paper.status))
        self.classify(use_saved=True)

    def open_pdf(self):
        paper = self.selected_paper()
        if paper is None:
            return
        target = paper.archived_to or paper.source
        if not target.is_file():
            messagebox.showerror('PDF fehlt', 'Die Datei ist an diesem Ort nicht mehr vorhanden.', parent=self.root)
            return
        if os.name == 'nt':
            os.startfile(str(target))
        else:
            webbrowser.open(target.resolve().as_uri())

    def undo(self):
        if not Path(self.folder.get()).is_dir():
            return
        try:
            store = ArchiveStore(self.folder.get())
            row = store.last_move()
            if row is None:
                messagebox.showinfo('Rückgängig', 'In diesem Archiv gibt es keine bestätigte Verschiebung zum Rückgängigmachen.', parent=self.root)
                return
        except Exception as error:
            messagebox.showerror('Rückgängig', str(error), parent=self.root)
            return
        if not messagebox.askyesno('Letzte Einsortierung rückgängig?',
                f'{row["target"]}\n→ {row["source"]}\n\nNur die unveränderte PDF wird zurückverschoben. Vorhandene Dateien werden nicht überschrieben.',
                parent=self.root, default='no'):
            return
        def done(result):
            operation, source = result
            if self.collection:
                for index, paper in enumerate(self.collection.papers):
                    if paper.archived_to == store.path(operation['target']):
                        paper.archived_to, paper.status = None, 'Offen'
                        paper.metadata = Metadata(**json.loads(operation['old_metadata']))
                        self.paper_tree.item(str(index), values=(paper.source.name, paper.topic, paper.status))
            self.status.set(f'Rückgängig: {source.name}')
            self.append_log(f'Zurückverschoben: {source}')
        self.start(lambda: undo_last(store), done)

    def clear_cache(self):
        if not Path(self.folder.get()).is_dir():
            return
        if messagebox.askyesno('Analysecache leeren?',
                'Gespeicherte Texte, Zusammenfassungen und Zuordnungen dieses Archivs löschen? '
                'Die nächste LLM-Analyse benötigt erneut Anfragen. Regeln, PDFs und Rückgängig-Verlauf bleiben erhalten.',
                parent=self.root, default='no'):
            try:
                ArchiveStore(self.folder.get()).clear_cache()
                self.status.set('Analysecache geleert. Archivregeln und PDFs bleiben erhalten.')
                if self.collection:
                    self.invalidate()
            except Exception as error:
                messagebox.showerror('Cache', str(error), parent=self.root)

    def audit_archive(self):
        if not self.saved_profile:
            messagebox.showinfo('Archivregeln fehlen', 'Bitte zuerst die Themen dieses Archivs bestätigen und speichern.', parent=self.root)
            return
        if messagebox.askyesno('Bestehende Sammlung neu prüfen?',
                'Auch PDFs in den bereits verwalteten Themenordnern prüfen? Es entstehen zunächst nur Vorschläge. '
                'Jede Verschiebung braucht weiterhin deine Einzelbestätigung.', parent=self.root, default='no'):
            self.audit_next = True
            self.analyze()

    def propose_additions(self):
        if not self.collection or self.collection.mode != MODES[2]:
            messagebox.showinfo('Themenvorschläge', 'Inhaltliche Ergänzungen sind im LLM-Modus verfügbar. Lokale Regeln kannst du selbst bearbeiten.', parent=self.root)
            return
        collection = self.collection
        documents, filenames = {}, {}
        for index, paper in enumerate(collection.papers, 1):
            if paper.analysis and paper.status != 'Duplikat':
                identifier = f'PDF{index}'
                documents[identifier], filenames[identifier] = paper.analysis, paper.source.name
        def job():
            return self.with_client(collection.mode, self.analysis_account, self.analysis_model,
                lambda client: review_topic_fit(client, documents, collection.accepted_topics))
        def done(result):
            review, additions = result
            known = {topic.name.casefold() for topic in collection.topics}
            for item in additions:
                if item['name'].casefold() not in known:
                    collection.topics.append(Topic(item['name'], item['description'],
                        [filenames[i] for i in item['documents']], included=False, origin='suggested'))
            self.fit_review.set(review)
            self.render_topics()
            self.tabs.select(self.topic_page)
        self.start(job, done)

    def correction_rules(self):
        if not self.collection:
            return
        store = ArchiveStore(self.collection.folder)
        suggestions = store.correction_suggestions()
        if not suggestions:
            messagebox.showinfo('Regelvorschläge', 'Noch keine wiederholten Korrekturen für dasselbe Thema vorhanden.', parent=self.root)
            return
        for item in suggestions:
            topic = next((t for t in self.collection.topics if t.name == item['name']), None)
            if topic is None or not item['keywords']:
                continue
            if messagebox.askyesno('Regeländerung als Entwurf übernehmen?',
                    f'{item["count"]} verschiedene PDFs wurden nach {topic.name} korrigiert.\n'
                    f'Gemeinsame Begriffe: {", ".join(item["keywords"])}\n\n'
                    'Diese Begriffe als Keyword-Ergänzung in den Themenentwurf übernehmen? '
                    'Gespeichert wird erst nach der anschließenden Themenbestätigung.', parent=self.root, default='no'):
                topic.keywords = tuple(dict.fromkeys([*topic.keywords, *item['keywords']]))
                topic.note = 'Ergänzung aus bestätigten Korrekturen — bitte prüfen'
                self.pending_correction_ids.extend(item['ids'])
                self.ready = False
        self.render_topics()
        self.tabs.select(self.topic_page)

    def next_paper(self):
        for i, paper in enumerate(self.collection.papers):
            if paper.status == 'Offen':
                self.paper_tree.selection_set(str(i))
                self.paper_tree.see(str(i))
                return
        if not self.paper_tree.selection() and self.paper_tree.get_children():
            self.paper_tree.selection_set(self.paper_tree.get_children()[0])
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
