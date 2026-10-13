"""Synthetic PDFs are generated temporarily; no research papers are included."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.analysis import Metadata, UNCLASSIFIED, classify, guess_metadata, read_pdf
from src.files import destination, filename, move_pdf, scan_pdfs
from src.main import review


def make_pdf(path, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 50 750 Td (Digital history 2024) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_metadata({'/Title': 'A Test Paper', '/Author': 'Test Author'})
    if encrypted:
        writer.encrypt('test-password')
    writer.write(path)


class ArchiveTests(unittest.TestCase):
    def test_keywords_boundaries_repetition_and_ties(self):
        topic, matches = classify('DIGITAL\nHISTORY digital history migrationist')
        self.assertEqual(topic, 'Digital History')
        self.assertEqual(matches['Digital History'], ['digital history'])
        self.assertEqual(matches['Social History'], [])
        self.assertEqual(classify('digital history migration')[0], UNCLASSIFIED)
        self.assertEqual(classify('unrelated text')[0], UNCLASSIFIED)

    def test_metadata_fallbacks(self):
        result = guess_metadata({}, 'Example article\nBy: Ada Example\nPublished 2020', Path('paper.pdf'))
        self.assertEqual(result, Metadata('Example article', 'Ada Example', '2020'))
        self.assertEqual(guess_metadata({}, '', Path('paper.pdf')),
                         Metadata('paper', 'UnknownAuthor', 'UnknownYear'))

    def test_pdf_extraction_and_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'paper.pdf'
            make_pdf(path)
            metadata, text = read_pdf(path)
            self.assertEqual(metadata, Metadata('A Test Paper', 'Test Author', '2024'))
            self.assertIn('Digital history', text)
            make_pdf(path, encrypted=True)
            with self.assertRaises(ValueError):
                read_pdf(path)
            path.write_bytes(b'not a pdf')
            with self.assertRaises(Exception):
                read_pdf(path)

    def test_collision_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input.PDF'
            source.write_bytes(b'original')
            (root / 'notes.txt').write_text('ignore me')
            self.assertEqual(scan_pdfs(root), [source])
            metadata = Metadata('../unsafe:title?', 'A/B', '2024')
            self.assertEqual(filename(metadata), 'A_B_2024_unsafe_title.pdf')
            target = destination(root / 'out', UNCLASSIFIED, metadata)
            move_pdf(source, target)
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b'original')
            self.assertTrue(destination(root / 'out', UNCLASSIFIED, metadata).name.endswith('_2.pdf'))
            source.write_bytes(b'new')
            with self.assertRaises(FileExistsError):
                move_pdf(source, target)
            self.assertEqual(source.read_bytes(), b'new')
            self.assertEqual(target.read_bytes(), b'original')

    def test_failed_copy_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'in.pdf', Path(temp) / 'out.pdf'
            source.write_bytes(b'original')
            with patch('src.files.shutil.copyfileobj', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    move_pdf(source, target)
            self.assertTrue(source.exists())
            self.assertFalse(target.exists())

    def test_change_skip_and_accept(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / 'in.pdf', Path(temp) / 'out'
            source.write_bytes(b'original')
            metadata = Metadata('Old', 'UnknownAuthor', 'UnknownYear')
            answers = iter(['c', 'New title', 'Ada', '2024', '6', 's'])
            self.assertFalse(review(source, metadata, UNCLASSIFIED, {}, output,
                                    ask=lambda _: next(answers), show=lambda _: None))
            self.assertTrue(source.exists())
            self.assertFalse(output.exists())
            self.assertTrue(review(source, metadata, UNCLASSIFIED, {}, output,
                                   ask=lambda _: 'a', show=lambda _: None))
            self.assertTrue((output / UNCLASSIFIED / 'Ada_2024_New_title.pdf').exists())


if __name__ == '__main__':
    unittest.main()
