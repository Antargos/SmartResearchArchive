"""Persistent archive behavior uses synthetic PDFs and simulated model responses."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from src.analysis import Metadata, guess_metadata
from src.archive_store import ArchiveStore, existing_profile
from src.archive_workflow import (STRATEGIES, analyze_cached_sections, archive_one, assign_archive,
                                   imported_topics, prepare_archive, profile_topics, undo_last)
from src.chatgpt_auth import ConnectionError
from src.desktop_service import MODES, Topic, approved_mapping
from src.semantic import review_topic_fit
from test_archive import make_pdf


class Model:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []
    def json_result(self, instructions, content):
        self.calls.append((instructions, content))
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


def definitions():
    return [Topic('Methods', 'Historical digital methods', keywords=('digital history',))]


class FilenameMetadataTests(unittest.TestCase):
    def test_numbered_author_title_year_and_canonical_names(self):
        for filename in ('02_Jones_Origins_2006.pdf', 'Jones_2006_Origins.pdf', 'Jones - 2006 - Origins.pdf'):
            with self.subTest(filename=filename):
                metadata = guess_metadata({}, '', Path(filename))
                self.assertEqual((metadata.author, metadata.year, metadata.title), ('Jones', '2006', 'Origins'))
                self.assertEqual(metadata.sources['author'], 'Dateiname')

    def test_embedded_author_priority_and_conflicts_are_visible(self):
        result = guess_metadata({'/Author': 'Ada Smith', '/Title': 'Printed Title'}, 'A paper from 1999', Path('Jones_2006_Origins.pdf'))
        self.assertEqual(result.author, 'Ada Smith')
        self.assertEqual(result.year, '2006')
        self.assertEqual(result.sources['author'], 'PDF-Metadaten')
        self.assertTrue(result.warnings)

    def test_plain_titles_do_not_become_authors_and_placeholders_are_ignored(self):
        result = guess_metadata({'/Author': 'Microsoft Word'}, 'Interesting article\n2020', Path('Digital_History_Methods.pdf'))
        self.assertEqual(result.author, 'UnknownAuthor')
        self.assertEqual(result.sources['author'], 'Nicht erkannt')


class ArchiveWorkflowTests(unittest.TestCase):
    def test_profile_roundtrip_and_unapproved_additions_are_not_saved(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ArchiveStore(Path(temporary))
            topics = definitions() + [Topic('Unapproved', 'Not accepted', included=False)]
            store.save_profile(topics, 'local')
            profile = existing_profile(store.root)
            self.assertEqual([t.name for t in profile_topics(profile)], ['Methods'])
            self.assertEqual(profile['topics'][0]['keywords'], ['digital history'])
            self.assertNotIn('Unapproved', str(profile))

    def test_unsafe_profile_and_duplicate_topics_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ArchiveStore(Path(temporary))
            for topics in ([Topic('../escape', 'Unsafe')], [Topic('Methods', 'A'), Topic('methods', 'B')]):
                with self.subTest(topics=topics), self.assertRaises(ValueError):
                    store.save_profile(topics, 'local')
            self.assertIsNone(store.profile())

    def test_profile_paths_survive_renaming_archive_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old, new = base / 'old', base / 'new'
            old.mkdir()
            store = ArchiveStore(old)
            store.save_profile(definitions(), 'local')
            self.assertEqual(old.parent, new.parent)
            old.rename(new)
            self.assertEqual(existing_profile(new)['topics'][0]['name'], 'Methods')

    def test_local_term_proposals_are_unselected_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            collection = prepare_archive(root, MODES[0], STRATEGIES[2], [])
            self.assertTrue(collection.topics)
            self.assertTrue(all(not t.included for t in collection.topics))

    def test_duplicates_in_input_and_existing_topics_are_not_analyzed_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            (root / 'b.pdf').write_bytes((root / 'a.pdf').read_bytes())
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], definitions())
            self.assertEqual([p.status for p in collection.papers], ['Offen', 'Duplikat'])
            store = ArchiveStore(root)
            assign_archive(collection, approved_mapping(collection), store)
            target = archive_one(collection, collection.papers[0], collection.papers[0].metadata, 'Methods', store)
            model = Model([])
            again = prepare_archive(root, MODES[2], STRATEGIES[0], definitions(), 'model', model)
            self.assertEqual(again.papers[0].status, 'Duplikat')
            self.assertEqual(again.papers[0].duplicate_of, target)
            self.assertEqual(model.calls, [])
            self.assertTrue((root / 'b.pdf').exists())

    def test_completed_model_analysis_and_assignment_are_reused_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            model = Model([{'summary': 'Historical methods', 'evidence': ['Digital history']},
                           {'topic': 'Methods', 'reason': 'Digital historical method'}])
            collection = prepare_archive(root, MODES[2], STRATEGIES[0], definitions(), 'mock', model)
            assign_archive(collection, approved_mapping(collection), ArchiveStore(root), 'mock', model)
            self.assertEqual(len(model.calls), 2)
            resumed = Model([])
            again = prepare_archive(root, MODES[2], STRATEGIES[0], definitions(), 'mock', resumed)
            assign_archive(again, approved_mapping(again), ArchiveStore(root), 'mock', resumed)
            self.assertEqual(again.papers[0].topic, 'Methods')
            self.assertEqual(resumed.calls, [])

    def test_interrupted_long_pdf_reuses_completed_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ArchiveStore(Path(temporary))
            text = 'Digital history ' + 'x' * 12000
            first = Model([{'summary': 'First section', 'evidence': ['Digital history']}, ConnectionError('offline')])
            with self.assertRaises(ConnectionError):
                analyze_cached_sections(first, text, store, 'digest', 'mock')
            resumed = Model([{'summary': 'Second section', 'evidence': ['xxx']}, {'summary': 'Combined history'}])
            result = analyze_cached_sections(resumed, text, store, 'digest', 'mock')
            self.assertEqual(result['summary'], 'Combined history')
            self.assertEqual(len(resumed.calls), 2)

    def test_rule_change_invalidates_only_assignment_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            first = Model([{'summary': 'Historical methods', 'evidence': ['Digital history']},
                           {'topic': 'Methods', 'reason': 'First interpretation'}])
            collection = prepare_archive(root, MODES[2], STRATEGIES[0], definitions(), 'mock', first)
            store = ArchiveStore(root)
            assign_archive(collection, {'Methods': 'First rule'}, store, 'mock', first)
            second = Model([{'topic': 'Methods', 'reason': 'Changed rule'}])
            again = prepare_archive(root, MODES[2], STRATEGIES[0], definitions(), 'mock', second)
            assign_archive(again, {'Methods': 'Different rule'}, store, 'mock', second)
            self.assertEqual(len(second.calls), 1)
            self.assertEqual(again.papers[0].reason, 'Changed rule')

    def test_deferred_and_skipped_decisions_survive_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], definitions())
            paper = collection.papers[0]
            paper.metadata.author = 'Manually Checked'
            paper.reason = 'Needs bibliographic review'
            store = ArchiveStore(root)
            for status in ('Später prüfen', 'Übersprungen'):
                store.save_decision(paper, status)
                again = prepare_archive(root, MODES[0], STRATEGIES[0], definitions())
                self.assertEqual(again.papers[0].status, status)
                self.assertEqual(again.papers[0].metadata.author, 'Manually Checked')
                self.assertEqual(again.papers[0].reason, 'Needs bibliographic review')

    def test_undo_restores_original_name_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'Original.pdf'
            make_pdf(original)
            data = original.read_bytes()
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], definitions())
            store = ArchiveStore(root)
            assign_archive(collection, approved_mapping(collection), store)
            paper = collection.papers[0]
            target = archive_one(collection, paper, Metadata('Changed Title', 'Ada', '2024'), 'Methods', store)
            self.assertFalse(original.exists())
            original.write_bytes(b'occupied')
            with self.assertRaises(ValueError):
                undo_last(store)
            self.assertEqual(original.read_bytes(), b'occupied')
            original.unlink()
            row, restored = undo_last(store)
            self.assertEqual(restored, collection.folder / 'Original.pdf')
            self.assertEqual(restored.read_bytes(), data)
            self.assertFalse(target.exists())
            self.assertIsNone(store.last_move())

    def test_undo_rejects_changed_archived_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], definitions())
            store = ArchiveStore(root)
            assign_archive(collection, approved_mapping(collection), store)
            paper = collection.papers[0]
            target = archive_one(collection, paper, paper.metadata, 'Methods', store)
            target.write_bytes(target.read_bytes() + b'changed')
            with self.assertRaises(ValueError):
                undo_last(store)
            self.assertTrue(target.exists())

    def test_correction_suggestions_need_two_distinct_pdfs_and_never_edit_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_pdf(root / 'a.pdf')
            make_pdf(root / 'b.pdf')
            (root / 'b.pdf').write_bytes((root / 'b.pdf').read_bytes() + b'\n%different')
            collection = prepare_archive(root, MODES[0], STRATEGIES[1], definitions())
            store = ArchiveStore(root)
            store.save_profile(definitions(), 'local')
            before = deepcopy(store.profile())
            for paper in collection.papers:
                store.correction(paper, 'Other', 'Methods')
            suggestions = store.correction_suggestions()
            self.assertEqual(suggestions[0]['count'], 2)
            self.assertEqual(store.profile(), before)
            store.resolve_corrections(suggestions[0]['ids'])
            self.assertEqual(store.correction_suggestions(), [])

    def test_existing_subfolders_are_imported_only_as_unconfirmed_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Märzrevolution').mkdir()
            (root / 'Unclassified').mkdir()
            (root / '.private').mkdir()
            topics = imported_topics(root)
            self.assertEqual([t.name for t in topics], ['Märzrevolution'])
            self.assertFalse(topics[0].included)
            self.assertEqual(topics[0].keywords, ())

    def test_llm_review_keeps_user_topics_and_additions_separate(self):
        rules = {'Labor': {'description': 'Workers', 'keywords': ['wages']}}
        before = deepcopy(rules)
        model = Model([{'review': 'PDF1 concerns migration; Labor is a narrower research focus.',
                        'topics': [{'name': 'Migration', 'description': 'Population movements', 'documents': ['PDF1']}]}])
        review, additions = review_topic_fit(model, {'PDF1': {'summary': 'Migration history'}}, rules)
        self.assertEqual(rules, before)
        self.assertEqual(additions[0]['name'], 'Migration')
        self.assertIn('PDF1', review)

    def test_empty_llm_addition_list_is_valid(self):
        model = Model([{'review': 'Your rules fit this collection.', 'topics': []}])
        review, additions = review_topic_fit(model, {'PDF1': {'summary': 'Labor history'}}, {'Labor': 'Workers'})
        self.assertEqual(additions, [])

    def test_existing_collection_is_only_included_in_explicit_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'Methods').mkdir()
            (root / 'Unrelated Folder').mkdir()
            make_pdf(root / 'Methods' / 'Existing.pdf')
            make_pdf(root / 'Unrelated Folder' / 'NeverRead.pdf')
            store = ArchiveStore(root)
            store.save_profile(definitions(), 'local')
            normal = prepare_archive(root, MODES[0], STRATEGIES[0], definitions())
            self.assertEqual(normal.papers, [])
            audited = prepare_archive(root, MODES[0], STRATEGIES[0], definitions(), include_archived=True)
            self.assertEqual(len(audited.papers), 1)
            self.assertNotEqual(audited.papers[0].status, 'Duplikat')
            assign_archive(audited, approved_mapping(audited), store)
            paper = audited.papers[0]
            target = archive_one(audited, paper, paper.metadata, 'Methods', store)
            self.assertEqual(target.parent, store.root / 'Methods')
            self.assertTrue((root / 'Unrelated Folder' / 'NeverRead.pdf').exists())


if __name__ == '__main__':
    unittest.main()
