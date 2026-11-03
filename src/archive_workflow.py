"""Persistent archive workflows; no GUI, implicit rule changes or hidden retries."""

from dataclasses import asdict
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .analysis import Metadata, UNCLASSIFIED, guess_metadata, read_pdf
from .archive_store import ArchiveStore, stable_key
from .chatgpt_auth import ModelOutputError
from .desktop_service import (MODES, Cancelled, CancellableClient, Collection, Paper, Topic,
                              approved_mapping, assign, fingerprint)
from .files import content_hash, is_link, move_pdf, safe_part, scan_pdfs, valid_topic_name
from .semantic import analyze_document, classify_batch, generate_keywords, propose_topics, review_topic_fit
from .ocr import extract_document

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
                    progress=lambda message: None, cancelled=lambda: False, include_archived=False,
                    ocr_enabled=True, llm_workers=2, combine=False):
    if mode != MODES[2] and strategy == STRATEGIES[2]:
        raise ValueError('Lokale Themenvorschläge entfallen. Bitte eigene Themen und Keywords festlegen.')
    store = ArchiveStore(folder)
    store.recover_moves()
    folder = store.root
    paths = scan_pdfs(folder)
    if include_archived:
        folders = dict.fromkeys([t.name for t in initial_topics] + store.get('managed_folders', []) + [UNCLASSIFIED])
        for name in folders:
            subfolder = folder / name
            if valid_topic_name(name) and subfolder.is_dir() and not is_link(subfolder):
                paths.extend(scan_pdfs(subfolder))
    if mode == MODES[2] and client is None:
        raise ValueError('Bitte ChatGPT verbinden und ein Modell auswählen.')
    # A local/hybrid run never summarizes PDFs, even if a caller supplies a client.
    model = CancellableClient(client, cancelled) if mode == MODES[2] else None
    topics = [Topic(**asdict(topic)) for topic in initial_topics]
    names = [topic.name for topic in topics]
    progress('Vorhandene Themenordner auf identische PDFs prüfen …')
    duplicate_index = store.duplicate_index(names, cancelled)
    papers, errors, summaries, filenames = [], [], {}, {}
    for number, path in enumerate(paths, 1):
        if cancelled():
            raise Cancelled()
        progress(f'{number}/{len(paths)}: {path.name}')
        digest = ''
        try:
            digest = fingerprint(path)
            duplicate = duplicate_index.get(digest)
            if duplicate and duplicate.resolve() != path.resolve() and duplicate.exists() and content_hash(duplicate) == digest:
                papers.append(Paper(path, guess_metadata({}, '', path), digest, '', status='Duplikat',
                                    duplicate_of=duplicate, reason=f'Identische PDF bereits vorhanden: {duplicate}.'))
                continue
            duplicate_index[digest] = path
            metadata, text, complete = extract_document(path, store, digest, ocr_enabled, progress, cancelled)
            if fingerprint(path) != digest:
                raise ValueError('Datei wurde während der Analyse geändert.')
        except Cancelled:
            raise
        except Exception as error:
            errors.append(f'{path.name}: {error}')
            if path.exists():
                papers.append(Paper(path, guess_metadata({}, '', path), digest, '', status='Später prüfen',
                                    reason=f'PDF konnte nicht gelesen werden: {error}', analysis_problem=str(error)))
            continue
        paper = Paper(path, metadata, digest, text)
        if not complete or not text.strip():
            paper.status = 'Später prüfen'
            paper.analysis_problem = 'Textebene unvollständig oder nicht lesbar. Bitte OCR-Hinweise prüfen.'
            paper.reason = paper.analysis_problem
        decision = store.decision(path, digest)
        if decision and decision['status'] in ('Später prüfen', 'Übersprungen'):
            paper.status = decision['status']
            paper.metadata = Metadata(**decision['metadata'])
            paper.reason = decision.get('reason', paper.reason)
            paper.topic = decision.get('topic', UNCLASSIFIED)
            if paper.topic not in names:
                paper.topic = UNCLASSIFIED
        papers.append(paper)
    if model:
        approved = approved_mapping(Collection(folder, mode, [], topics, [])) if combine and strategy == STRATEGIES[0] else None
        def summarize(paper):
            # Text participates in the key: a successful later OCR cannot reuse a
            # summary of an older, incomplete text layer.
            digest = stable_key([paper.fingerprint, paper.text])
            key = stable_key([PIPELINE, digest, model_key])
            cached = store.cached('summary', key)
            if cached:
                paper.analysis, paper.analysis_problem = cached['analysis'], cached['problem']
                progress(f'{paper.source.name}: gespeicherte LLM-Auswertung wiederverwendet.')
            else:
                progress(f'{paper.source.name}: LLM-Inhaltsanalyse …')
                try:
                    paper.analysis = analyze_cached_sections(model, paper.text, store, digest, model_key, approved)
                except ModelOutputError as error:
                    paper.analysis_problem = str(error)
                store.checkpoint('summary', key, {'analysis': paper.analysis, 'problem': paper.analysis_problem})
            if paper.analysis_problem:
                paper.status, paper.reason = 'Später prüfen', paper.analysis_problem
        eligible = [p for p in papers if p.status == 'Offen']
        # Only two jobs are ever in flight. Finish current work on failure but do
        # not queue the rest or retry provider/usage errors.
        new = [p for p in eligible if store.cached('summary', stable_key(
            [PIPELINE, stable_key([p.fingerprint, p.text]), model_key])) is None]
        allowed_new = {id(p) for p in new[:50]}
        eligible = [p for p in eligible if p not in new or id(p) in allowed_new]
        workers = max(1, min(2, int(llm_workers)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(0, len(eligible), workers):
                if cancelled():
                    raise Cancelled()
                pending = [executor.submit(summarize, p) for p in eligible[start:start + workers]]
                for future in pending:
                    future.result()
        if len(new) > 50:
            raise ValueError('50 neue LLM-Dokumente erreicht. Gespeicherte Arbeit bleibt erhalten; erneut starten, um fortzusetzen.')
    for index, paper in enumerate(papers, 1):
        if paper.analysis:
            identifier = f'PDF{index}'
            summaries[identifier], filenames[identifier] = paper.analysis, paper.source.name
            errors.extend(f'{paper.source.name}: {warning}' for warning in paper.analysis.get('warnings', []))
        if paper.analysis_problem:
            errors.append(f'{paper.source.name}: {paper.analysis_problem}')
    review = ''
    if strategy == STRATEGIES[2]:
        proposed = propose_topics(model, summaries)
        topics = [Topic(item['name'], item['description'], [filenames[i] for i in item['documents']],
                        origin='suggested') for item in proposed]
    elif model and strategy in (STRATEGIES[1], STRATEGIES[3]) and summaries:
        rules = {t.name: {'description': t.description, 'keywords': list(t.keywords)} for t in topics if t.included}
        review, additions = review_topic_fit(model, summaries, rules)
        topics.extend(Topic(item['name'], item['description'], [filenames[i] for i in item['documents']],
                            included=False, origin='suggested', note='Neuer LLM-Vorschlag — nur nach Bestätigung')
                      for item in additions)
    if cancelled():
        raise Cancelled()
    return Collection(folder, mode, papers, topics, errors, topic_review=review, include_archived=include_archived)


def keyword_draft(topics, client, store, model_key):
    selected = [topic for topic in topics if topic.included]
    # Validate names/descriptions without requiring local keywords yet.
    definitions = approved_mapping(Collection(store.root, MODES[2], [], selected, []))
    key = stable_key(['keywords-v1', model_key, definitions])
    proposed = store.cached('keyword_draft', key)
    if proposed is None:
        proposed = generate_keywords(client, definitions)
        store.checkpoint('keyword_draft', key, proposed)
    return proposed


def analyze_cached_sections(client, text, store, digest, model_key, topics=None):
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
    return analyze_document(SectionCache(), text, topics)


def assign_archive(collection, topics, store, model_key='', client=None,
                   progress=lambda message: None, cancelled=lambda: False):
    pending = []
    model = CancellableClient(client, cancelled) if client else None
    def save(paper, key, result):
        paper.topic, paper.reason = result
        store.checkpoint('assignment', key, {'topic': paper.topic, 'reason': paper.reason})
    for paper in collection.papers:
        if cancelled():
            raise Cancelled()
        if paper.status != 'Offen':
            continue
        key = stable_key([PIPELINE, paper.fingerprint, stable_key(paper.text), collection.mode, model_key, topics])
        cached = store.cached('assignment', key)
        combined = (paper.analysis or {}).get('assignment', {})
        if cached:
            paper.topic, paper.reason = cached['topic'], cached['reason']
            progress(f'{paper.source.name}: gespeicherte Zuordnung wiederverwendet.')
        elif collection.mode == MODES[2] and combined.get('rules') == topics:
            save(paper, key, (combined['topic'], combined['reason']))
        elif collection.mode == MODES[2] and paper.analysis and topics and not paper.analysis_problem:
            pending.append((paper, key))
        else:
            one = Collection(collection.folder, collection.mode, [paper], collection.topics, collection.errors)
            assign(one, topics, client, progress, cancelled)
            save(paper, key, (paper.topic, paper.reason))
    for start in range(0, len(pending), 4):
        batch = pending[start:start + 4]
        progress(f'LLM-Zuordnung: {start + 1}–{start + len(batch)} von {len(pending)} PDFs …')
        if model is None:
            raise ValueError('ChatGPT-Verbindung fehlt.')
        if len(batch) == 1:
            # Preserve the simple single-document contract and error isolation.
            paper, key = batch[0]
            one = Collection(collection.folder, collection.mode, [paper], collection.topics, collection.errors)
            assign(one, topics, client, progress, cancelled)
            save(paper, key, (paper.topic, paper.reason))
            continue
        documents = {f'PDF{i}': {'summary': paper.analysis['summary'], 'evidence': paper.analysis['evidence']}
                     for i, (paper, key) in enumerate(batch, 1)}
        try:
            results = classify_batch(model, documents, topics)
        except ModelOutputError as error:
            results = {identifier: (UNCLASSIFIED, str(error)) for identifier in documents}
        for i, (paper, key) in enumerate(batch, 1):
            save(paper, key, results[f'PDF{i}'])
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
