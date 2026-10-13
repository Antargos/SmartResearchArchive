"""Collection-based suggestions, safe custom topics and the complete CLI flow."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.analysis import Metadata, UNCLASSIFIED, classify
from src.files import destination
from src.suggestions import Suggestion, approve_topics, suggest_topics, terms_in
from test_archive import make_pdf


class SuggestionTests(unittest.TestCase):
    def test_coverage_not_repetition_and_deterministic_ranking(self):
        documents = [('one.pdf', 'Digital history migration migration migration'),
                     ('two.pdf', 'Digital history archives')]
        suggestions = suggest_topics(documents)
        self.assertEqual(suggestions[0], Suggestion('digital history', ('one.pdf', 'two.pdf')))
        self.assertNotIn('migration', [item.term for item in suggestions])
        self.assertEqual(suggestions, suggest_topics(list(reversed(documents))))

    def test_no_false_phrases_across_stopwords_numbers_or_punctuation(self):
        terms = terms_in('migration and memory; archives 2024 history. digital humanities')
        self.assertNotIn('migration memory', terms)
        self.assertNotIn('memory archives', terms)
        self.assertNotIn('archives history', terms)
        self.assertIn('digital humanities', terms)

    def test_empty_single_and_disjoint_collections(self):
        self.assertEqual(suggest_topics([]), [])
        self.assertEqual(suggest_topics([('blank.pdf', '')]), [])
        self.assertEqual(suggest_topics([('a.pdf', 'migration'), ('b.pdf', 'archives')]), [])
        self.assertEqual(suggest_topics([('a.pdf', 'migration'), ('blank.pdf', '')])[0].term,
                         'migration')

    def test_edit_accept_and_skip(self):
        answers = iter(['c', 'Migration History', 'migration, refugees', 'a', 's'])
        topics = approve_topics([Suggestion('migration', ('a.pdf', 'b.pdf')),
                                 Suggestion('memory', ('a.pdf', 'b.pdf'))],
                                ask=lambda _: next(answers), show=lambda _: None)
        self.assertEqual(topics, {'Migration History': ('migration', 'refugees')})
        self.assertEqual(classify('refugees', topics)[0], 'Migration History')
        self.assertEqual(classify('archive', topics)[0], UNCLASSIFIED)
        self.assertEqual(classify('migration', {})[0], UNCLASSIFIED)

    def test_unsafe_reserved_and_duplicate_folder_names(self):
        metadata = Metadata('Paper', 'Ada', '2024')
        for name in ('../escape', 'CON', 'LPT1', '/outside', 'name.', ' name'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                destination(Path('archive'), name, metadata, {name: ('term',)})
        answers = iter(['c', 'CON', '', 'a', 'c', 'History', '', 'a',
                        'c', 'history', '', 'a', 's'])
        topics = approve_topics([Suggestion('migration', ('a.pdf',)),
                                 Suggestion('memory', ('a.pdf',))],
                                ask=lambda _: next(answers), show=lambda _: None)
        self.assertEqual(list(topics), ['History'])

    def test_cli_topics_only_and_sort_with_approved_collection_topic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            incoming, archive = root / 'input', root / 'archive'
            incoming.mkdir()
            for name in ('a.pdf', 'b.pdf'):
                make_pdf(incoming / name)
            command = [sys.executable, '-m', 'src.main', '--input', str(incoming),
                       '--output', str(archive)]
            preview = subprocess.run(command + ['--topics-only'], input='a\n',
                                     text=True, capture_output=True, check=True)
            self.assertIn('digital history', preview.stdout)
            self.assertEqual(len(list(incoming.glob('*.pdf'))), 2)
            self.assertFalse(archive.exists())
            result = subprocess.run(command + ['--suggest-topics'], input='a\na\na\n',
                                    text=True, capture_output=True, check=True)
            self.assertNotIn('Could not finish', result.stdout)
            self.assertEqual(list(incoming.glob('*.pdf')), [])
            self.assertEqual(len(list((archive / 'Digital History').glob('*.pdf'))), 2)


if __name__ == '__main__':
    unittest.main()
