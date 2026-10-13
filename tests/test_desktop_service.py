"""Exercise in-place sorting and desktop stages without opening any GUI."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.analysis import Metadata, UNCLASSIFIED
from src.desktop_service import (MODES, Cancelled, Topic, approved_mapping, archive_paper,
                                  assign, prepare, skip_paper)
from src.files import content_hash, move_pdf
from test_archive import make_pdf


class DesktopTests(unittest.TestCase):
    def test_downloads_folder_in_place_after_individual_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ('first.pdf', 'second.PDF'):
                make_pdf(folder / name)
            nested = folder / 'Already Sorted'
            nested.mkdir()
            make_pdf(nested / 'old.pdf')
            collection = prepare(folder, MODES[0])
            self.assertEqual(len(collection.papers), 2)
            assign(collection, approved_mapping(collection))
            self.assertTrue((folder / 'first.pdf').exists())  # Analysis never moves.
            target = archive_paper(collection, collection.papers[0], Metadata('Edited Title', 'Ada', '2024'), 'Digital History')
            self.assertEqual(target, collection.folder / 'Digital History' / 'Ada_2024_Edited_Title.pdf')
            self.assertTrue(target.exists())
            self.assertFalse((folder / 'first.pdf').exists())
            skip_paper(collection.papers[1])
            self.assertTrue((folder / 'second.PDF').exists())
            self.assertTrue((nested / 'old.pdf').exists())
            with self.assertRaises(ValueError):
                archive_paper(collection, collection.papers[0], Metadata('Title', 'Ada', '2024'), 'Digital History')

    def test_changed_pdf_invalid_name_and_duplicate_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            collection = prepare(folder, MODES[0])
            assign(collection, approved_mapping(collection))
            paper = collection.papers[0]
            original = paper.source.read_bytes()
            paper.source.write_bytes(original + b'changed')
            with self.assertRaises(ValueError):
                archive_paper(collection, paper, paper.metadata, paper.topic)
            paper.source.write_bytes(original)
            with self.assertRaises(ValueError):
                archive_paper(collection, paper, paper.metadata, '../escape')
            target_folder = folder / 'Digital History'
            target_folder.mkdir()
            existing = target_folder / 'Test_Author_2024_A_Test_Paper.pdf'
            existing.write_bytes(b'existing paper')
            target = archive_paper(collection, paper, paper.metadata, paper.topic)
            self.assertTrue(target.name.endswith('_2.pdf'))
            self.assertEqual(existing.read_bytes(), b'existing paper')

    def test_copy_verification_preserves_changed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source, target = folder / 'in.pdf', folder / 'out.pdf'
            source.write_bytes(b'original')
            expected = content_hash(source)
            def changed_copy(original, archived):
                archived.write(b'changed')
            with patch('src.files.shutil.copyfileobj', side_effect=changed_copy), self.assertRaises(ValueError):
                move_pdf(source, target, expected)
            self.assertTrue(source.exists())
            self.assertFalse(target.exists())

    def test_topics_limits_duplicates_manual_and_no_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            collection = prepare(folder, MODES[1])
            collection.topics = [Topic('Manual Topic', 'migration, refugees')]
            self.assertEqual(approved_mapping(collection), {'Manual Topic': ('migration', 'refugees')})
            collection.topics.append(Topic('manual topic', 'history'))
            with self.assertRaises(ValueError):
                approved_mapping(collection)
            collection.topics = [Topic(f'Topic {i}', 'history') for i in range(6)]
            with self.assertRaises(ValueError):
                approved_mapping(collection)
            collection.topics = []
            assign(collection, approved_mapping(collection))
            self.assertEqual(collection.papers[0].topic, UNCLASSIFIED)

    def test_cancellation_and_unreadable_pdf_do_not_move_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'good.pdf')
            (folder / 'bad.pdf').write_bytes(b'not a PDF')
            with self.assertRaises(Cancelled):
                prepare(folder, MODES[0], cancelled=lambda: True)
            collection = prepare(folder, MODES[0])
            self.assertEqual(len(collection.papers), 1)
            self.assertEqual(len(collection.errors), 1)
            with self.assertRaises(Cancelled):
                assign(collection, approved_mapping(collection), cancelled=lambda: True)
            self.assertTrue((folder / 'good.pdf').exists())
            self.assertTrue((folder / 'bad.pdf').exists())

    def test_content_based_desktop_flow_uses_approved_descriptions(self):
        class Model:
            def __init__(self):
                self.results = iter([
                    {'summary': 'Digital historical methods', 'evidence': ['Digital history']},
                    {'topics': [{'name': 'Historical Methods', 'description': 'Methods used in research', 'documents': ['PDF1']}]},
                    {'topic': 'Historical Methods', 'reason': 'The paper studies historical methods.'}])
            def json_result(self, instructions, content):
                return next(self.results)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            client = Model()
            collection = prepare(folder, MODES[2], client)
            self.assertEqual(collection.topics[0].name, 'Historical Methods')
            assign(collection, approved_mapping(collection), client)
            self.assertEqual(collection.papers[0].topic, 'Historical Methods')
            self.assertTrue((folder / 'a.pdf').exists())


if __name__ == '__main__':
    unittest.main()
