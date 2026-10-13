"""Propose vocabulary from the collection; humans decide what counts as a topic."""

from collections import defaultdict
from dataclasses import dataclass
import re

from .analysis import UNCLASSIFIED, normalize
from .files import safe_part, valid_topic_name

# A deliberately small, editable English/German stop list. It removes common
# function words and publication boilerplate, not every uninformative term.
STOPWORDS = set('''the and for with from this that these those have has were was
are not but can will into over under between through their our your its they
also more most some than then only such which what when where who how all any
der die das den dem des ein eine einer eines einen einem und oder aber mit von
auf aus bei zum zur fuer für über unter zwischen durch sich ist sind war waren
als auch nach nicht werden wird wurde wurden diese dieser dieses diesen im in
an am zu es er sie wir ihr man so et al doi http https www com org
abstract introduction conclusion conclusions references bibliography copyright
reserved rights journal volume issue page pages author authors university
paper article study studies research results method methods figure table
einleitung literatur fazit zusammenfassung seite seiten autor autoren'''.split())


@dataclass
class Suggestion:
    term: str
    documents: tuple[str, ...]


def terms_in(text: str) -> set[str]:
    """Unigrams and adjacent bigrams. Never bridge a stopword or punctuation."""
    tokens = re.findall(r'[^\W\d_]+|\d+|[^\w\s]', normalize(text), re.UNICODE)
    found = set()
    previous = None
    for token in tokens:
        if not token.isalpha() or len(token) < 4 or token in STOPWORDS:
            previous = None
            continue
        found.add(token)
        if previous:
            found.add(previous + ' ' + token)
        previous = token
    return found


def suggest_topics(documents, limit=10) -> list[Suggestion]:
    """Rank by document coverage, then prefer phrases, then alphabetical order.

    Each input is (filename, extracted text). A keyword gets at most one vote
    per PDF; two PDFs must mention it unless only one readable PDF is available.
    """
    evidence = defaultdict(set)
    readable = [(name, text) for name, text in documents if text.strip()]
    for name, text in readable:
        for term in terms_in(text):
            evidence[term].add(name)
    minimum = 1 if len(readable) == 1 else 2
    ranked = sorted((term for term, names in evidence.items() if len(names) >= minimum),
                    key=lambda term: (-len(evidence[term]), -len(term.split()), term))
    suggestions = []
    for term in ranked:
        # Hide a unigram if a selected phrase contains it with identical evidence.
        if any(term in item.term.split() and evidence[term] == set(item.documents)
               for item in suggestions):
            continue
        suggestions.append(Suggestion(term, tuple(sorted(evidence[term]))))
        if len(suggestions) >= limit:
            break
    return suggestions


def approve_topics(suggestions, ask=input, show=print, maximum=5):
    """Explicit acceptance builds a session-only name → keywords mapping."""
    accepted = {}
    for item in suggestions:
        show(f'\nSuggestion: {item.term} — found in {len(item.documents)} PDF(s)')
        show('Evidence: ' + ', '.join(item.documents))
        name = safe_part(item.term.title(), 'Topic', 60).replace('_', ' ')
        keywords = (item.term,)
        while True:
            show(f'Topic: {name}; keywords: {", ".join(keywords)}')
            choice = ask('[A]ccept / [C]hange / [S]kip: ').strip().lower()
            if choice in ('s', 'skip'):
                break
            if choice in ('c', 'change'):
                new_name = ask('Topic name (Enter keeps it; ASCII letters/numbers/spaces): ').strip()
                new_words = ask('Keywords separated by commas (Enter keeps them): ').strip()
                if new_name:
                    name = new_name
                if new_words:
                    keywords = tuple(dict.fromkeys(normalize(word) for word in new_words.split(',')
                                                   if normalize(word)))
                continue  # Show the changed suggestion before accepting it.
            if choice in ('a', 'accept'):
                if (not valid_topic_name(name) or name.casefold() == UNCLASSIFIED.casefold()
                        or name.casefold() in {label.casefold() for label in accepted}
                        or not keywords):
                    show('Invalid or duplicate name/empty keywords. Change or skip this suggestion.')
                    continue
                accepted[name] = keywords
                break
            show('Please choose Accept, Change or Skip.')
        if len(accepted) >= maximum:
            break
    show(f'\nAccepted topics for this run: {len(accepted)}')
    if not accepted:
        show('No topics accepted; all files will use Unclassified unless skipped.')
    return accepted
