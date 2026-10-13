# Project journal

## 13 October 2026 — Start of version 1

### Goal
Build a beginner-friendly local PDF organizer for the course Applied Programming Projects.

### Starting point
The repository contained a short README only. The available conversation describes
the workflow but does not specify the five topic names. Initial editable categories:
Digital History, Archival Studies, Social History, Political History, Cultural History.

### Decisions
- Use pypdf for text and embedded metadata; no OCR, ML, embeddings, or external API.
- Prefer readable functions and standard-library unittest over a framework.
- Count each distinct matching keyword once; tied or zero scores mean Unclassified.
- Require human acceptance after every preview, including after corrections.
- Avoid overwriting files; add numeric suffixes for duplicate names.
- Ignore all PDFs and local input/archive folders in Git.
- No CSV, reference-manager integration, open-source license, or LICENSE file.

### AI assistance
Codex drafted the implementation, documentation and tests based on the user's scope.
Automated checks are recorded below; personal review and evaluation with 20–50
lawfully obtained research PDFs remain tasks for the project owner. This entry does
not claim that the owner has already reviewed or understood the generated code.

### Limitations and next evaluation
Metadata is a suggestion, not verified bibliographic data. Scans without a text layer
cannot be read. Keywords may occur in references or unrelated contexts. Evaluate
metadata accuracy, classification and usability with a local collection; record
mistakes and corrections here without uploading the papers.

### Automated validation
Six unittest cases passed with Python 3.12.14 and pypdf 6.10.0: synthetic PDF text
and metadata extraction, corrupt/encrypted input, keyword boundaries and ties,
collision protection, failed-copy cleanup, and Change/Skip/Accept behavior.
Test fixtures are generated temporarily, not committed. Initial sandbox execution
could not write to the system temporary folder; the authorized run outside the
sandbox passed. Real-paper accuracy and personal code review remain unverified.

## 13 October 2026 — Experimental collection topic suggestions

### Goal and branch
User requested topics suggested from the supplied PDFs on a separate GitHub branch:
`feature/pdf-topic-suggestions`. The original main branch remains unchanged.

### Method and decisions
Use recurring words and adjacent pairs, an editable English/German stop list,
and document coverage scoring. Require two readable PDFs as evidence except in
a single-document collection. Prefer phrases at equal coverage and use alphabetical
order to make ranking reproducible. Show filenames as evidence. This is an explicit
vocabulary heuristic, not semantic interpretation, ML or embeddings.

Users accept/change/skip candidates and define up to five session-only topics.
The approved mapping feeds the existing classifier and file review. Folder names
are validated against path traversal, duplicate names and Windows reserved names.
`--topics-only` reviews suggestions without moving files; `--suggest-topics` then
continues to the usual per-file acceptance. No accepted topics means Unclassified.
Local input is meant by supplied PDFs; no upload interface is implemented.

### AI assistance and evaluation
Codex drafted this extension and regression tests. Tests exercise document coverage,
phrase boundaries, empty/single/disjoint collections, edits and rejected names,
plus the complete CLI with generated PDFs. Actual scholarly usefulness still needs
human evaluation on a local research collection; generic terms and references can
produce weak suggestions. Topics are not persisted and collection text stays in
memory during a run. Personal understanding/review is not claimed by this entry.

### Validation result
All 12 tests passed with Python 3.12.14 and pypdf 6.10.0, including the six original
regression cases and six new collection/CLI cases. Temporary PDFs were created
inside the writable workspace and removed by the tests. No PDFs were committed.

## 13 October 2026 — ChatGPT plan and semantic analysis

### Goal and branch
User chose an external LLM and authorized a new branch using Sign in with ChatGPT:
`feature/chatgpt-semantic-topics`, based on `feature/pdf-topic-suggestions`.
Main and the vocabulary branch remain unchanged. This explicitly expands the
initial no-ML scope into an optional LLM experiment; no embeddings are introduced.

### Implementation and decisions
Follow the documented dynamic registration, loopback callback, PKCE/state/nonce,
signed identity verification and explicit plan-usage scope. Save issued client IDs
separately per verified account, a stable installation host ID and protected local
credentials. Windows uses DPAPI; POSIX uses owner-only file permissions. Serialize
runs/refreshes. Never read Codex/browser credentials or use private browser APIs.
No API-key billing fallback, no new license and no repository PDFs.

Discover the connected account's models. Request streamed, unstored Responses API
results; reject failures, incomplete streams and invalid JSON. Summarize all text
sections and check short quotations against extracted text. Suggest common topics
from document summaries, require human topic approval, then classify semantically
and reuse the original safe Accept/Change/Skip file review. Model output does not
execute tools or choose arbitrary paths. Explicit external-processing consent is
required at runtime. No summaries/index are persisted; credentials are ignored.

### Tests and remaining evaluation
25 tests passed with Python 3.12.14, pypdf 6.10.0 and cryptography 50.0.2. Coverage
includes all original regressions, the browser-flow contract with a simulated
callback, signed/tampered JWTs, rejected state/client/scope, rotating refresh,
logout failures, DPAPI roundtrip, complete/failed streams, verified quotations,
semantic topic validation, consent cancellation, topic-only preview and file moves
with synthetic PDFs and simulated provider responses. No real account tokens or
PDF text were submitted in these tests. Live sign-in/account eligibility and
real-paper quality remain unverified and require the user's browser authorization.

### AI assistance and limitations
Codex drafted the integration using official OpenAI documentation and wrote offline
tests. The OAuth modules are intentionally isolated from the simple local workflow,
but add complexity to explain in the course. Model summaries can omit nuance;
exact quotes only establish that wording exists. Limits: 50 input PDFs and 240,000
characters per PDF. Eligibility/preview capabilities may change; see README links.
Personal understanding and review by the owner are not claimed by this entry.
