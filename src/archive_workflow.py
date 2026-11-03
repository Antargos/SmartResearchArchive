"""Persistent archive workflows; no GUI, implicit rule changes or hidden retries."""

from dataclasses import asdict
import json
from pathlib import Path

from .analysis import Metadata, UNCLASSIFIED, guess_metadata, read_pdf
from .archive_store import ArchiveStore, stable_key
from .chatgpt_auth import ModelOutputError
from .desktop_service import (MODES, Cancelled, CancellableClient, Collection, Paper, Topic,
                              approved_mapping, assign, fingerprint)
from .files import content_hash, is_link, move_pdf, safe_part, scan_pdfs, valid_topic_name
from .semantic import analyze_document, propose_topics, review_topic_fit
from .suggestions import suggest_topics

STRATEGIES = ('Archivregeln verwenden', 'Eigene Themen', 'Themen vorschlagen', 'Vorhandene Unterordner übernehmen')
PIPELINE = 'archive-v2-1'


def profile_topics(profile):
    return [Topic(item['name'], item['description'], keywords=tuple(item['keywords']), origin='saved')
            for item in (profile or {}).get('topics', [])]


def imported_topics(folder):
    return [Topic(path.name, f'Forschungsinhalte zum Thema {path.name}', included=False, origin='import',
                  note='Vorhandener Ordner: Beschreibung und Keywords bitte einmalig prüfen.')
            for path in sorted(Path(folder).iterdir(), key=lambda p: p.name.casefold())
            if path.is_dir() and not is_link(path) and valid_topic_name(path.name)
            and path.name.casefold() != UNCLASSIFIED.casefold()]


def prepare_archive(folder, mode, strategy, initial_topics, model_key='', client=None,
                    progress=lambda message: None, cancelled=lambda: False):
    store = ArchiveStore(folder)
    store.recover_moves()
    folder = store.root
    paths = scan_pdfs(folder)
    if mode == MODES[2] and client is None:
        raise ValueError('Bitte ChatGPT verbinden und ein Modell auswählen.')
    model = CancellableClient(client, cancelled) if client else None
    topics = [Topic(**asdict(topic)) for topic in initial_topics]
    names = [topic.name for topic in topics]
    progress('Vorhandene Themenordner auf identische PDFs prüfen …')
    duplicate_index = store.duplicate_index(names, cancelled)
    papers, errors, summaries, filenames = [], [], {}, {}
    uncached_requests = 0
    for number, path in enumerate(paths, 1):
        if cancelled():
            raise Cancelled()
        progress(f'{number}/{len(paths)}: {path.name}')
        digest = ''
        try:
            digest = fingerprint(path)
            duplicate = duplicate_index.get(digest)
            if duplicate and duplicate.exists() and content_hash(duplicate) == digest:
                paper = Paper(path, guess_metadata({}, '', path), digest, '', status='Duplikat', duplicate_of=duplicate,
                              reason=f'Identische PDF bereits vorhanden: {duplicate}. Nicht erneut ans LLM gesendet.')
                papers.append(paper)
                continue
            duplicate_index[digest] = path
            extraction_key = stable_key([PIPELINE, digest, path.name])
            extracted = store.cached('extraction', extraction_key)
            if extracted:
                metadata, text = Metadata(**extracted['metadata']), extracted['text']
                progress(f'{path.name}: gespeicherte Textextraktion wiederverwendet.')
            else:
                metadata, text = read_pdf(path)
                if fingerprint(path) != digest:
                    raise ValueError('Datei wurde während der Analyse geändert.')
                store.checkpoint('extraction', extraction_key, {'metadata': asdict(metadata), 'text': text})
        except Exception as error:
            errors.append(f'{path.name}: {error}')
            if path.exists():
                paper = Paper(path, guess_metadata({}, '', path), digest, '',
                              status='Später prüfen', reason=f'PDF konnte nicht gelesen werden: {error}',
                              analysis_problem=str(error))
                papers.append(paper)
            continue
        analysis, problem = None, ''
        if model:
            summary_key = stable_key([PIPELINE, digest, model_key])
            cached = store.cached('summary', summary_key)
            if cached:
                analysis, problem = cached['analysis'], cached['problem']
                progress(f'{path.name}: gespeicherte LLM-Auswertung wiederverwendet.')
            elif text.strip():
                if uncached_requests >= 50:
                    raise ValueError('50 neue LLM-Dokumente erreicht. Gespeicherte Arbeit bleibt erhalten; erneut starten, um fortzusetzen.')
                uncached_requests += 1
                try:
                    analysis = analyze_cached_sections(model, text, store, digest, model_key)
                except ModelOutputError as error:
                    problem = str(error)
                    errors.append(f'{path.name}: {problem} Unclassified; weitere PDFs werden verarbeitet.')
                    progress(errors[-1])
                store.checkpoint('summary', summary_key, {'analysis': analysis, 'problem': problem})
        paper = Paper(path, metadata, digest, text, analysis, analysis_problem=problem)
        if problem or not text.strip():
            paper.status = 'Später prüfen'
            paper.reason = problem or 'Kein auswertbarer Text. OCR ist nicht enthalten; bitte manuell prüfen.'
        decision = store.decision(path, digest)
        if decision and decision['status'] in ('Später prüfen', 'Übersprungen'):
            paper.status = decision['status']
            paper.metadata = Metadata(**decision['metadata'])
            paper.reason = decision.get('reason', paper.reason)
            paper.topic = decision.get('topic', UNCLASSIFIED)
            if paper.topic not in names:
                paper.topic = UNCLASSIFIED
        papers.append(paper)
        if analysis:
            identifier = f'PDF{len(papers)}'
            summaries[identifier], filenames[identifier] = analysis, path.name
            for warning in analysis.get('warnings', []):
                errors.append(f'{path.name}: {warning}')
    review = ''
    if strategy == STRATEGIES[2]:
        if model:
            proposed = propose_topics(model, summaries)
            topics = [Topic(item['name'], item['description'], [filenames[i] for i in item['documents']],
                            origin='suggested') for item in proposed]
        else:
            # A term helper, not an automatic scholarly taxonomy; never preselected.
            proposed = suggest_topics([(p.source.name, p.metadata.title + '\n' + p.text[:3000])
                                       for p in papers if p.status != 'Duplikat'])
            topics = [Topic(safe_part(item.term.title(), 'Thema', 60).replace('_', ' '),
                            f'Begriffshilfe: {item.term}', list(item.documents), included=False,
                            keywords=(item.term,), origin='suggested', note='Ungeprüfte lokale Begriffshilfe')
                      for item in proposed]
            review = 'Lokale Vorschläge sind nur Begriffshilfen. Bitte Themen selbst sinnvoll benennen und auswählen.'
    elif model and strategy in (STRATEGIES[1], STRATEGIES[3]) and summaries:
        rules = {t.name: {'description': t.description, 'keywords': list(t.keywords)} for t in topics if t.included}
        review, additions = review_topic_fit(model, summaries, rules)
        topics.extend(Topic(item['name'], item['description'], [filenames[i] for i in item['documents']],
                            included=False, origin='suggested', note='Neuer LLM-Vorschlag — nur nach Bestätigung')
                      for item in additions)
    if cancelled():
        raise Cancelled()
    return Collection(folder, mode, papers, topics, errors, topic_review=review)


def analyze_cached_sections(client, text, store, digest, model_key):
    """Persist each successful request so an interrupted long PDF resumes mid-file."""
    class SectionCache:
        def json_result(self, instructions, content):
            key = stable_key([PIPELINE, digest, model_key, instructions, content])
            cached = store.cached('model_request', key)
            if cached is not None:
                return cached
            value = client.json_result(instructions, content)
            store.checkpoint('model_request', key, value)
            return value
    return analyze_document(SectionCache(), text)


def assign_archive(collection, topics, store, model_key='', client=None,
                   progress=lambda message: None, cancelled=lambda: False):
    for paper in collection.papers:
        if cancelled():
            raise Cancelled()
        if paper.status != 'Offen':
            continue
        key = stable_key([PIPELINE, paper.fingerprint, collection.mode, model_key, topics])
        cached = store.cached('assignment', key)
        if cached:
            paper.topic, paper.reason = cached['topic'], cached['reason']
            progress(f'{paper.source.name}: gespeicherte Zuordnung wiederverwendet.')
        else:
            one = Collection(collection.folder, collection.mode, [paper], collection.topics, collection.errors)
            assign(one, topics, client, progress, cancelled)
            store.checkpoint('assignment', key, {'topic': paper.topic, 'reason': paper.reason})
    collection.accepted_topics = topics
    return collection


def archive_one(collection, paper, metadata, topic, store):
    from .desktop_service import archive_paper
    suggested = paper.topic
    target = archive_paper(collection, paper, metadata, topic, archive=store)
    store.index_file(target, paper.fingerprint)
    store.correction(paper, suggested, topic)
    return target


def undo_last(store):
    row = store.last_move()
    if row is None:
        raise ValueError('Keine bestätigte Einsortierung zum Rückgängigmachen vorhanden.')
    source, target = store.path(row['source']), store.path(row['target'])
    if source.exists():
        raise ValueError('Der ursprüngliche Dateiname ist inzwischen belegt. Es wird nichts überschrieben.')
    if not target.is_file() or content_hash(target) != row['digest']:
        raise ValueError('Die einsortierte PDF fehlt oder wurde verändert. Rückgängig wurde abgebrochen.')
    store.mark_move(row['id'], 'undo_pending')
    move_pdf(target, source, expected_hash=row['digest'])
    store.mark_move(row['id'], 'undone')
    with store.connection() as db:
        db.execute('DELETE FROM files WHERE path=?', (row['target'],))
        db.execute('DELETE FROM decisions WHERE path=? AND digest=?', (row['source'], row['digest']))
        db.execute('DELETE FROM corrections WHERE digest=? AND chosen=? AND applied=0', (row['digest'], row['topic']))
    return row, source
