"""The desktop workflow without GUI code: analyze, review, then explicitly move."""

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re

from .analysis import Metadata, TOPICS, UNCLASSIFIED, classify, read_pdf
from .files import destination, is_link, move_pdf, safe_part, scan_pdfs, valid_topic_name
from .semantic import analyze_document, classify_semantically, propose_topics
from .suggestions import suggest_topics

MODES = ('Feste Themen (lokal)', 'Themen aus Begriffen (lokal)', 'Inhaltliche Analyse mit ChatGPT')


class Cancelled(Exception):
    pass


@dataclass
class Paper:
    source: Path
    metadata: Metadata
    fingerprint: str
    text: str
    analysis: dict | None = None
    topic: str = UNCLASSIFIED
    reason: str = ''
    status: str = 'Offen'


@dataclass
class Topic:
    name: str
    description: str
    documents: list[str] = field(default_factory=list)
    included: bool = True


@dataclass
class Collection:
    folder: Path
    mode: str
    papers: list[Paper]
    topics: list[Topic]
    errors: list[str]
    accepted_topics: dict = field(default_factory=dict)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class CancellableClient:
    def __init__(self, client, cancelled):
        self.client, self.cancelled = client, cancelled

    def json_result(self, *args):
        if self.cancelled():
            raise Cancelled()
        result = self.client.json_result(*args)
        if self.cancelled():
            raise Cancelled()
        return result


def prepare(folder, mode, client=None, progress=lambda message: None, cancelled=lambda: False):
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir() or mode not in MODES:
        raise ValueError('Bitte einen Ordner und eine Analyseart auswählen.')
    paths = scan_pdfs(folder)
    if mode == MODES[2] and len(paths) > 50:
        raise ValueError('Für ChatGPT bitte höchstens 50 PDFs direkt im ausgewählten Ordner verwenden.')
    if mode == MODES[2] and client is None:
        raise ValueError('Bitte zuerst ChatGPT verbinden und ein Modell auswählen.')
    model = CancellableClient(client, cancelled) if client else None
    papers, errors, summaries, filenames = [], [], {}, {}
    for index, path in enumerate(paths, 1):
        if cancelled():
            raise Cancelled()
        progress(f'{index}/{len(paths)}: {path.name}')
        try:
            before = fingerprint(path)
            metadata, text = read_pdf(path)
            if fingerprint(path) != before:
                raise ValueError('Datei wurde während des Einlesens geändert.')
        except Exception as error:
            errors.append(f'{path.name}: {error}')
            continue
        analysis = analyze_document(model, text) if model else None
        paper = Paper(path, metadata, before, text, analysis)
        papers.append(paper)
        if analysis:
            document_id = f'PDF{len(papers)}'
            summaries[document_id] = analysis
            filenames[document_id] = path.name
    if mode == MODES[0]:
        topics = [Topic(name, ', '.join(words)) for name, words in TOPICS.items()]
    elif mode == MODES[1]:
        candidates = suggest_topics([(p.source.name, p.text) for p in papers])
        topics = [Topic(safe_part(item.term.title(), 'Topic', 60).replace('_', ' '),
                        item.term, list(item.documents), included=index < 5)
                  for index, item in enumerate(candidates)]
    else:
        topics = [Topic(item['name'], item['description'],
                        [filenames[document_id] for document_id in item['documents']])
                  for item in propose_topics(model, summaries)]
    if cancelled():
        raise Cancelled()
    return Collection(folder, mode, papers, topics, errors)


def approved_mapping(collection):
    selected = [topic for topic in collection.topics if topic.included]
    if len(selected) > 5:
        raise ValueError('Bitte höchstens fünf Themen auswählen.')
    names, result = set(), {}
    for topic in selected:
        name = topic.name.strip()
        if (not valid_topic_name(name) or name.casefold() == UNCLASSIFIED.casefold()
                or name.casefold() in names or not topic.description.strip()):
            raise ValueError('Themen brauchen eindeutige, sichere Namen und eine Beschreibung oder Keywords.')
        if len(topic.description) > 800:
            raise ValueError('Themenbeschreibung bitte auf 800 Zeichen begrenzen.')
        names.add(name.casefold())
        if collection.mode == MODES[2]:
            result[name] = topic.description.strip()
        else:
            words = tuple(dict.fromkeys(word.strip().casefold() for word in topic.description.split(',')
                                        if word.strip()))
            if not words:
                raise ValueError('Mindestens ein Keyword pro Thema ist erforderlich.')
            result[name] = words
    return result


def assign(collection, topics, client=None, progress=lambda message: None, cancelled=lambda: False):
    model = CancellableClient(client, cancelled) if client else None
    for index, paper in enumerate(collection.papers, 1):
        if cancelled():
            raise Cancelled()
        progress(f'Zuordnung {index}/{len(collection.papers)}: {paper.source.name}')
        if collection.mode == MODES[2]:
            if model is None:
                raise ValueError('ChatGPT-Verbindung fehlt.')
            paper.topic, paper.reason = classify_semantically(model, paper.analysis, topics)
        else:
            paper.topic, matches = classify(paper.text, topics)
            paper.reason = '\n'.join(f'{name}: {len(words)} Punkte ({", ".join(words) or "keine Treffer"})'
                                     for name, words in matches.items())
    collection.accepted_topics = topics
    return collection


def archive_paper(collection, paper, metadata, topic):
    """One explicit confirmation moves one unchanged top-level PDF in place."""
    if paper.status != 'Offen':
        raise ValueError('Diese Datei wurde bereits bearbeitet.')
    if (is_link(paper.source) or paper.source.resolve().parent != collection.folder
            or not paper.source.is_file() or fingerprint(paper.source) != paper.fingerprint):
        raise ValueError('Die Quelldatei wurde geändert oder verschoben. Bitte neu analysieren.')
    if not metadata.title.strip() or not metadata.author.strip():
        raise ValueError('Titel und Autor dürfen nicht leer sein; UnknownAuthor ist erlaubt.')
    if not re.fullmatch(r'\d{4}|UnknownYear', metadata.year):
        raise ValueError('Jahr: vier Ziffern oder UnknownYear.')
    target = destination(collection.folder, topic, metadata, collection.accepted_topics)
    if target.parent.exists() and not target.parent.is_dir():
        raise ValueError('Ein Eintrag mit dem Themennamen existiert bereits und ist kein Ordner.')
    move_pdf(paper.source, target, expected_hash=paper.fingerprint)
    paper.metadata, paper.topic, paper.status = metadata, topic, 'Einsortiert'
    return target


def skip_paper(paper):
    if paper.status == 'Offen':
        paper.status = 'Übersprungen'
