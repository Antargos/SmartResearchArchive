"""Optional external analysis. Local keyword modes never instantiate this client."""

from .analysis import read_pdf
from .chatgpt_auth import ConnectionError, connect, load, session_lock
from .chatgpt_client import ChatGPTClient
from .semantic import (analyze_document, approve_semantic_topics, classify_semantically,
                       propose_topics)


def run_chatgpt(papers, output, review, model=None, topics_only=False,
                ask=input, show=print):
    if not papers:
        return
    if len(papers) > 50:
        raise ConnectionError('Use at most 50 PDFs per ChatGPT run.')
    show('This mode sends extracted PDF text and generated summaries to OpenAI. '
         'It uses your ChatGPT plan limits. No original PDF upload or API-key billing fallback.')
    if ask('Send this collection for external analysis? [y/N]: ').strip().lower() != 'y':
        show('Cancelled; no document text sent and no files changed.')
        return
    with session_lock():
        state = load()
        profile = connect(state)
        selected = ChatGPTClient.choose_model(profile, model)
        show(f'Using ChatGPT plan, model: {selected}')
        client = ChatGPTClient(profile, selected, state)
        loaded, analyses, filenames = {}, {}, {}
        for number, source in enumerate(papers, 1):
            document_id = f'PDF{number}'
            try:
                metadata, text = read_pdf(source)
            except Exception:
                show(f'Could not read {source.name}; excluded from semantic analysis.')
                continue
            show(f'Analyzing {source.name}...')
            # Fail the run on provider/validation errors. Nothing has moved yet.
            analysis = analyze_document(client, text)
            loaded[document_id] = (source, metadata)
            filenames[document_id] = source.name
            if analysis:
                analyses[document_id] = analysis
                show('Summary: ' + analysis['summary'])
                for quote in analysis['evidence']:
                    show('Verified text excerpt: ' + quote)
            else:
                show('No extractable text; Unclassified. OCR is not included.')
        proposals = propose_topics(client, analyses)
        topics = approve_semantic_topics(proposals, filenames, ask=ask, show=show)
        if topics_only:
            show('Topic preview finished; no PDFs moved. Topics are session-only.')
            return
        for document_id, (source, metadata) in loaded.items():
            topic, reason = classify_semantically(client, analyses.get(document_id), topics)
            show(f'\nSuggested topic for {source.name}: {topic}\nModel reason: {reason}')
            show('The reason describes the original suggestion; you can change the topic below.')
            # Reuse the existing safe file review, passing approved names rather than
            # allowing an LLM-generated path or command to reach the filesystem.
            review(source, metadata, topic, {}, output, ask=ask, show=show,
                   topic_keywords=topics)
