"""Local, page-selective OCR. Originals are never rewritten or uploaded."""

from dataclasses import asdict
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from pypdf import PdfReader

from .analysis import Metadata, guess_metadata
from .archive_store import stable_key
from .desktop_service import Cancelled

OCR_VERSION = 'tesseract-deu-eng-220dpi-v1'


def tesseract_path():
    bundled = Path(sys.executable).parent / 'ocr' / 'tesseract.exe'
    candidates = [bundled, Path(os.environ.get('ProgramFiles', 'C:/Program Files')) /
                  'Tesseract-OCR' / 'tesseract.exe']
    return next((str(path) for path in candidates if path.is_file()), shutil.which('tesseract'))


def usable_text(text):
    letters = sum(character.isalpha() for character in text)
    return letters >= 20 and text.count('\ufffd') <= max(1, len(text) // 100)


def recognize_page(path, number, temporary_root, cancelled=lambda: False):
    executable = tesseract_path()
    if not executable:
        raise ValueError('Lokale OCR fehlt. Windows-Komplettpaket verwenden oder Tesseract installieren.')
    import pypdfium2 as pdfium
    with tempfile.TemporaryDirectory(prefix='ocr-', dir=temporary_root) as temporary:
        image_path = Path(temporary) / 'page.png'
        # Close all native PDFium objects before invoking OCR or moving a PDF.
        with pdfium.PdfDocument(str(path)) as pdf:
            page = pdf[number]
            width, height = page.get_size()
            scale = min(220 / 72, 5000 / max(width, height))
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            try:
                # Empty pages need no OCR request and do not invalidate a paper.
                if image.convert('L').point(lambda value: 0 if value > 245 else 255).getbbox() is None:
                    return None
                image.save(image_path)
            finally:
                image.close()
                bitmap.close()
                page.close()
        if cancelled():
            raise Cancelled()
        command = [executable, str(image_path), 'stdout', '-l', 'deu+eng', '--psm', '3']
        data = Path(executable).parent / 'tessdata'
        if data.is_dir():
            command.extend(['--tessdata-dir', str(data)])
        result = subprocess.run(command, capture_output=True, timeout=90,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if cancelled():
            raise Cancelled()
        if result.returncode:
            raise ValueError('OCR fehlgeschlagen: ' + result.stderr.decode('utf-8', errors='replace')[:350])
        return result.stdout.decode('utf-8', errors='replace').strip()


def extract_document(path, store, digest, enabled=True, progress=lambda message: None,
                     cancelled=lambda: False, recognizer=None):
    """Check every page, OCR only missing/broken layers, persist each success."""
    recognizer = recognizer or recognize_page
    key = stable_key(['extraction-v3', digest, path.name, enabled, OCR_VERSION])
    cached = store.cached('extraction', key)
    if cached:
        progress(f'{path.name}: gespeicherte Textebene wiederverwendet.')
        return Metadata(**cached['metadata']), cached['text'], True
    texts, warnings, complete, ocr_pages = [], [], True, []
    with path.open('rb') as source:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ValueError('Verschlüsselte PDF: bitte zuerst lokal entschlüsseln.')
        embedded = dict(reader.metadata or {})
        for number, page in enumerate(reader.pages):
            if cancelled():
                raise Cancelled()
            try:
                text = page.extract_text() or ''
            except Exception:
                text = ''
            # A short selectable cover heading alone is no reason to run OCR.
            resources = page.get('/Resources') or {}
            if hasattr(resources, 'get_object'):
                resources = resources.get_object()
            short_cover = text.strip() and not resources.get('/XObject') and sum(c.isalpha() for c in text) >= 3
            if not usable_text(text) and not short_cover:
                if not enabled:
                    complete = False
                    warnings.append(f'Seite {number + 1}: keine brauchbare Textebene; OCR ist ausgeschaltet.')
                else:
                    page_key = stable_key([digest, number, OCR_VERSION])
                    saved = store.cached('ocr_page', page_key)
                    try:
                        if saved is not None:
                            text = saved['text']
                        else:
                            progress(f'{path.name}: lokale OCR für Seite {number + 1}/{len(reader.pages)} …')
                            text = recognizer(path, number, store.directory, cancelled)
                            store.checkpoint('ocr_page', page_key, {'text': text})
                        ocr_pages.append(number + 1)
                        if text is not None and not usable_text(text):
                            raise ValueError('zu wenig verlässlich erkennbarer Text')
                    except Cancelled:
                        raise
                    except Exception as error:
                        complete = False
                        warnings.append(f'Seite {number + 1}: {error}')
            texts.append(text or '')
    metadata = guess_metadata(embedded, texts[0] if texts else '', path)
    metadata.warnings.extend(warnings)
    if ocr_pages:
        metadata.warnings.append('Lokale OCR auf Seite(n): ' + ', '.join(map(str, ocr_pages)) +
                                 '. OCR-Fehler sind möglich; Original bitte prüfen.')
    text = '\n'.join(texts)
    if complete:
        store.checkpoint('extraction', key, {'metadata': asdict(metadata), 'text': text})
    return metadata, text, complete


def ocr_self_test():
    """Actual raster PDF -> bundled renderer -> OCR check; no research material."""
    from PIL import Image, ImageDraw, ImageFont
    from .archive_store import ArchiveStore
    from .files import content_hash
    with tempfile.TemporaryDirectory(prefix='sra-ocr-check-') as temporary:
        root = Path(temporary)
        pdf = root / 'Synthetic_Scan.pdf'
        image = Image.new('RGB', (1700, 700), 'white')
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf'
        font = ImageFont.truetype(str(font_path), 48)
        ImageDraw.Draw(image).multiline_text((70, 90),
            'Digital history and medieval workshops\nHistorical research and archival studies\nHandwerk und Werkstatt im Mittelalter',
            font=font, fill='black', spacing=35)
        image.save(pdf, 'PDF', resolution=150)
        image.close()
        digest = content_hash(pdf)
        metadata, text, complete = extract_document(pdf, ArchiveStore(root), digest)
        if not complete or 'medieval workshops' not in text.casefold() or 'handwerk' not in text.casefold():
            raise RuntimeError('Actual OCR of the synthetic scan failed: ' + str(metadata.warnings))
        if content_hash(pdf) != digest:
            raise RuntimeError('OCR modified the source PDF.')
