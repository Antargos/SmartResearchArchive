"""Synthetic formatting and model-output regressions; no real research PDFs."""

from pathlib import Path
import tempfile
import unittest

from src.chatgpt_auth import ConnectionError, ModelOutputError
from src.desktop_service import MODES, assign, prepare
from src.evidence import source_excerpt
from src.semantic import analyze_document
from test_archive import make_pdf


class Responses:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def json_result(self, instructions, content):
        self.calls.append(content)
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


class EvidenceTests(unittest.TestCase):
    def test_exact_quote_is_unchanged(self):
        self.assertEqual(source_excerpt('A study of migration.', 'study of migration'), 'study of migration')

    def test_whitespace_and_nbsp_match_returns_the_original_excerpt(self):
        source = 'Historical\n  research\u00a0methods'
        self.assertEqual(source_excerpt(source, 'Historical research methods'), source)

    def test_ligatures_return_original_source_characters(self):
        self.assertEqual(source_excerpt('The ﬁnal ﬁnding.', 'final finding'), 'ﬁnal ﬁnding')

    def test_soft_and_line_hyphens_are_layout_only(self):
        source = 'indus-\ntrialization and migra\u00adtion'
        self.assertEqual(source_excerpt(source, 'industrialization and migration'), source)

    def test_changed_words_translation_and_ellipses_are_not_accepted(self):
        source = 'Migration increased in the nineteenth century.'
        for quote in ('Migration decreased', 'Wanderung nahm zu', 'Migration ... century'):
            with self.subTest(quote=quote):
                self.assertIsNone(source_excerpt(source, quote))

    def test_case_numbers_and_regular_hyphens_remain_significant(self):
        for source, quote in (('Working-class history', 'Workingclass history'),
                              ('In 2006', 'In 2007'), ('Migration', 'migration')):
            with self.subTest(source=source, quote=quote):
                self.assertIsNone(source_excerpt(source, quote))

    def test_partial_ligature_or_empty_quote_is_not_a_match(self):
        for quote in ('f', '', ' ', None, 123):
            with self.subTest(quote=quote):
                self.assertIsNone(source_excerpt('ﬁ', quote))

    def test_mixed_evidence_discards_only_unverified_quotes(self):
        client = Responses([{'summary': 'Historical methods.',
                             'evidence': ['Digital history', 'invented quotation']}])
        analysis = analyze_document(client, 'Digital\nhistory methods.')
        self.assertEqual(analysis['evidence'], ['Digital\nhistory'])
        self.assertEqual(len(analysis['warnings']), 1)
        self.assertNotIn('invented quotation', str(analysis))

    def test_no_verified_quote_rejects_the_document_analysis(self):
        client = Responses([{'summary': 'Historical methods.', 'evidence': ['invented quotation']}])
        with self.assertRaises(ModelOutputError):
            analyze_document(client, 'Digital history methods.')

    def test_later_unverified_section_does_not_silently_accept_partial_summary(self):
        client = Responses([{'summary': 'First section.', 'evidence': ['history']},
                            {'summary': 'Second section.', 'evidence': ['invented']}])
        with self.assertRaises(ModelOutputError):
            analyze_document(client, 'history ' + 'x' * 12000)

    def test_collection_continues_after_invalid_document_output(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            make_pdf(folder / 'b.pdf')
            client = Responses([
                {'summary': 'Unverified', 'evidence': ['invented quotation']},
                {'summary': 'Digital methods', 'evidence': ['Digital history']},
                {'topics': [{'name': 'Digital Methods', 'description': 'Historical methods', 'documents': ['PDF2']}]},
                {'topic': 'Digital Methods', 'reason': 'Historical methods'}])
            progress = []
            collection = prepare(folder, MODES[2], client, progress=progress.append)
            self.assertEqual(len(collection.papers), 2)
            self.assertTrue(collection.papers[0].analysis_problem)
            self.assertIsNone(collection.papers[0].analysis)
            self.assertEqual(collection.topics[0].documents, ['b.pdf'])
            assign(collection, {'Digital Methods': 'Historical methods'}, client)
            self.assertEqual(collection.papers[0].topic, 'Unclassified')
            self.assertEqual(collection.papers[1].topic, 'Digital Methods')
            self.assertEqual(len(client.calls), 4)  # No extra request for the failed document.
            self.assertTrue((folder / 'a.pdf').exists())
            self.assertTrue((folder / 'b.pdf').exists())
            self.assertTrue(any('weitere PDFs' in message for message in progress))

    def test_provider_failure_still_stops_without_repeating_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            make_pdf(folder / 'b.pdf')
            client = Responses([ConnectionError('usage limit')])
            with self.assertRaises(ConnectionError) as error:
                prepare(folder, MODES[2], client)
            self.assertIs(type(error.exception), ConnectionError)
            self.assertEqual(len(client.calls), 1)
            self.assertTrue((folder / 'a.pdf').exists())

    def test_bad_classification_is_isolated_to_one_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            make_pdf(folder / 'a.pdf')
            make_pdf(folder / 'b.pdf')
            collection = prepare(folder, MODES[0])
            collection.mode = MODES[2]
            for paper in collection.papers:
                paper.analysis = {'summary': 'History', 'evidence': ['Digital history']}
            client = Responses([{'topic': 'Nonexistent', 'reason': 'Invalid'},
                                {'topic': 'Methods', 'reason': 'Valid description'}])
            assign(collection, {'Methods': 'Research methods'}, client)
            self.assertEqual(collection.papers[0].topic, 'Unclassified')
            self.assertEqual(collection.papers[1].topic, 'Methods')
            self.assertEqual(len(collection.errors), 1)


if __name__ == '__main__':
    unittest.main()
