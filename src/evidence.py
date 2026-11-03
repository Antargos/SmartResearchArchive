"""Match PDF quotations despite layout differences, without fuzzy word matching."""

import re
import unicodedata

LINE_HYPHEN = re.compile(r'(?<=\w)[-\u2010][ \t]*\r?\n\s*(?=\w)')


def normalized_with_positions(text):
    """Keep source positions while folding whitespace and PDF typography.

    Only layout hyphens before line breaks and soft hyphens are removed. Regular
    hyphens, capitalization, punctuation, numbers and wording remain significant.
    NFKC handles ligatures such as ﬁ. Returned evidence always uses the source text.
    """
    skip = {i for match in LINE_HYPHEN.finditer(text) for i in range(match.start(), match.end())}
    letters, positions = [], []
    for index, character in enumerate(text):
        if index in skip or character == '\u00ad':
            continue
        for normalized in unicodedata.normalize('NFKC', character):
            if normalized.isspace():
                normalized = ' '
                if not letters or letters[-1] == ' ':
                    continue
            letters.append(normalized)
            positions.append(index)
    if letters and letters[-1] == ' ':
        letters.pop()
        positions.pop()
    return ''.join(letters), positions


def source_excerpt(fragment, quote):
    """Return an actual source substring, or None for a changed/invented quote."""
    if not isinstance(quote, str) or not quote.strip() or len(quote) > 200:
        return None
    if quote in fragment:
        return quote
    source, positions = normalized_with_positions(fragment)
    requested, _ = normalized_with_positions(quote)
    if not requested:
        return None
    offset = source.find(requested)
    while offset >= 0:
        excerpt = fragment[positions[offset]:positions[offset + len(requested) - 1] + 1]
        # A match must cover complete original characters, not half of a ligature.
        if len(excerpt) <= 400 and normalized_with_positions(excerpt)[0] == requested:
            return excerpt
        offset = source.find(requested, offset + 1)
    return None
