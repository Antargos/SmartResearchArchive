"""Three workflows, page-selective OCR and bounded model processing."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from pypdf import PdfReader, PdfWriter
from src.archive_store import ArchiveStore
from src.archive_workflow import (STRATEGIES, assign_archive, keyword_draft, prepare_archive)
from src.desktop_service import MODES, Collection, Paper, Topic, approved_mapping
from src.analysis import Metadata
from src.chatgpt_auth import ConnectionError, ModelOutputError
from src.ocr import extract_document
from src.semantic import classify_batch, generate_keywords
from test_archive import make_pdf


class Reply:
    def __init__(self, value):
        self.value, self.calls = value, []
    def json_result(self, instructions, content):
        self.calls.append(json.loads(content))
        return deepcopy(self.value)


def topics():
    return [Topic('Handwerk', 'Handwerk im frühen Mittelalter', keywords=('early medieval crafts',))]


class ProcessingTests(unittest.TestCase):
    def test_keyword_generation_never_renames_topics_and_sends_only_definitions(self):
        value = {'topics': [{'name': 'Handwerk', 'keywords': ['early medieval crafts', 'medieval metalwork',
                 'frühmittelalterliches Handwerk', 'frühmittelalterliche Werkstatt', 'medieval workshops'],
                 'reason': 'Specific subject and period phrases.'}]}
        model = Reply(value)
        definitions = {'Handwerk': 'Handwerk im frühen Mittelalter'}
        before = deepcopy(definitions)
        result = generate_keywords(model, definitions)
        self.assertEqual(definitions, before)
        self.assertEqual(model.calls, [{'user_topics': definitions}])
        self.assertEqual(len(result['Handwerk']['keywords']), 5)
        model.value['topics'][0]['name'] = 'Renamed'
        with self.assertRaises(ModelOutputError):
            generate_keywords(model, definitions)

    def test_hybrid_keyword_draft_is_cached_without_saving_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ArchiveStore(Path(temporary))
            definitions = topics()
            before = deepcopy(definitions)
            model = Reply({'topics': [{'name': 'Handwerk', 'keywords': ['craft one', 'craft two', 'craft three',
                                   'craft four', 'craft five'], 'reason': 'Draft only'}]})
            keyword_draft(definitions, model, store, 'mock')
            keyword_draft(definitions, model, store, 'mock')
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(definitions, before)
            self.assertIsNone(store.profile())
            store.save_profile(definitions, 'local', 'hybrid')
            self.assertEqual(store.profile()['workflow'], 'hybrid')

    def test_local_processing_never_sends_pdf_text_even_with_client(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            model = Mock()
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], topics(), client=model)
            assign_archive(collection, approved_mapping(collection), ArchiveStore(root), client=model)
            model.json_result.assert_not_called()

    def test_batch_assignment_reduces_four_requests_to_one_and_isolates_invalid_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            papers = [Paper(root / f'{i}.pdf', Metadata('Title', 'Ada', '2024'), str(i), 'Text',
                            {'summary': 'Handwerk', 'evidence': ['Text']}) for i in range(4)]
            collection = Collection(root, MODES[2], papers, topics(), [])
            model = Reply({'results': [{'id': f'PDF{i}', 'topic': 'Handwerk' if i != 2 else 'Invented',
                                       'reason': 'Subject match'} for i in range(1, 5)]})
            assign_archive(collection, approved_mapping(collection), ArchiveStore(root), 'mock', model)
            self.assertEqual(len(model.calls), 1)
            self.assertEqual([p.topic for p in papers], ['Handwerk', 'Unclassified', 'Handwerk', 'Handwerk'])
            assign_archive(collection, approved_mapping(collection), ArchiveStore(root), 'mock', model)
            self.assertEqual(len(model.calls), 1)

    def test_batch_rejects_unknown_ids_and_marks_missing_or_duplicate_ids(self):
        documents = {'PDF1': {}, 'PDF2': {}}
        model = Reply({'results': [{'id': 'PDF1', 'topic': 'Handwerk', 'reason': 'A'}]})
        result = classify_batch(model, documents, {'Handwerk': 'Craft'})
        self.assertEqual(result['PDF2'][0], 'Unclassified')
        model.value['results'][0]['id'] = 'unknown'
        with self.assertRaises(ModelOutputError):
            classify_batch(model, documents, {'Handwerk': 'Craft'})

    def test_known_rules_combine_summary_and_assignment_in_one_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            model = Reply({'summary': 'Digital historical craft methods', 'evidence': ['Digital history'],
                           'topic': 'Handwerk', 'reason': 'Confirmed research scope'})
            collection = prepare_archive(root, MODES[2], STRATEGIES[0], topics(), 'mock', model, combine=True)
            assign_archive(collection, approved_mapping(collection), ArchiveStore(root), 'mock', model)
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(collection.papers[0].topic, 'Handwerk')
            self.assertIn('allowed_topics', model.calls[0])

    def test_two_summaries_overlap_and_never_exceed_two_in_flight(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        active, maximum = 0, 0
        class Concurrent:
            def json_result(self, instructions, content):
                nonlocal active, maximum
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                try:
                    barrier.wait(timeout=10)
                    return {'summary': 'Historical methods', 'evidence': ['Digital history']}
                finally:
                    with lock:
                        active -= 1
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for i in range(4):
                make_pdf(root / f'{i}.pdf')
                with (root / f'{i}.pdf').open('ab') as file:
                    file.write(f'\n%{i}'.encode())
            collection = prepare_archive(root, MODES[2], STRATEGIES[0], topics(), 'mock', Concurrent())
            self.assertEqual(maximum, 2)
            self.assertTrue(all(p.analysis for p in collection.papers))

    def test_provider_failure_does_not_schedule_more_documents_and_keeps_completed_work(self):
        barrier, lock = threading.Barrier(2), threading.Lock()
        calls = []
        class Interrupted:
            def json_result(self, instructions, content):
                with lock:
                    index = len(calls)
                    calls.append(content)
                barrier.wait(timeout=10)
                if index == 0:
                    raise ConnectionError('usage limit')
                return {'summary': 'Historical methods', 'evidence': ['Digital history']}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for i in range(3):
                make_pdf(root / f'{i}.pdf')
                with (root / f'{i}.pdf').open('ab') as file:
                    file.write(f'\n%{i}'.encode())
            with self.assertRaises(ConnectionError):
                prepare_archive(root, MODES[2], STRATEGIES[0], topics(), 'mock', Interrupted())
            self.assertEqual(len(calls), 2)
            with ArchiveStore(root).connection() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM cache WHERE kind='summary'").fetchone()[0], 1)
            resumed = Reply({'summary': 'Historical methods', 'evidence': ['Digital history']})
            prepare_archive(root, MODES[2], STRATEGIES[0], topics(), 'mock', resumed)
            self.assertEqual(len(resumed.calls), 2)

    def test_ocr_only_missing_page_then_reuses_saved_text_and_keeps_pdf_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'mixed.pdf'
            make_pdf(path)
            writer = PdfWriter()
            writer.append(path)
            writer.add_blank_page(width=300, height=300)
            writer.write(path)
            data = path.read_bytes()
            store = ArchiveStore(root)
            recognize = Mock(return_value='Early medieval crafts and metal workshops')
            metadata, text, complete = extract_document(path, store, 'digest', recognizer=recognize)
            self.assertTrue(complete)
            self.assertIn('Digital history', text)
            self.assertIn('medieval crafts', text)
            self.assertEqual(recognize.call_args.args[1], 1)
            self.assertEqual(recognize.call_count, 1)
            extract_document(path, store, 'digest', recognizer=recognize)
            self.assertEqual(recognize.call_count, 1)
            self.assertEqual(path.read_bytes(), data)

    def test_failed_ocr_keeps_partial_text_out_of_llm(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'mixed.pdf'
            make_pdf(path)
            writer = PdfWriter()
            writer.append(path)
            writer.add_blank_page(width=300, height=300)
            writer.write(path)
            model = Mock()
            with patch('src.ocr.recognize_page', side_effect=ValueError('unreadable scan')):
                collection = prepare_archive(root, MODES[2], STRATEGIES[0], topics(), 'mock', model)
            self.assertEqual(collection.papers[0].status, 'Später prüfen')
            model.json_result.assert_not_called()

    def test_ocr_off_does_not_invoke_recognizer_for_missing_layers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'scan.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.write(path)
            recognize = Mock()
            metadata, text, complete = extract_document(path, ArchiveStore(root), 'digest', False, recognizer=recognize)
            self.assertFalse(complete)
            recognize.assert_not_called()

    def test_failed_later_ocr_page_resumes_without_repeating_successful_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'scan.pdf'
            writer = PdfWriter()
            for i in range(2):
                writer.add_blank_page(width=300, height=300)
            writer.write(path)
            store = ArchiveStore(root)
            first = Mock(side_effect=['Early medieval crafts and historical workshops', ValueError('bad page')])
            self.assertFalse(extract_document(path, store, 'digest', recognizer=first)[2])
            resumed = Mock(return_value='More historical workshops and craft production')
            self.assertTrue(extract_document(path, store, 'digest', recognizer=resumed)[2])
            self.assertEqual(resumed.call_count, 1)
            self.assertEqual(resumed.call_args.args[1], 1)

    @unittest.skipUnless(os.environ.get('SRA_OCR_TESTS') == '1', 'Real OCR runs in the Windows packaging check.')
    def test_real_scan_ocr(self):
        from src.ocr import ocr_self_test
        ocr_self_test()
