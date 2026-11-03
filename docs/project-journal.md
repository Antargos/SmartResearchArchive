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

## 13 October 2026 — Windows desktop release candidate

### Goal and branch
User requested a combined desktop app, downloadable EXE and installer on a separate
branch: `release/windows-desktop-v1`, based on the ChatGPT semantic branch. The GUI
lets users select any PDF folder and sort confirmed files into topic subfolders of
that same folder. Main and both earlier feature branches remain unchanged.

### Implementation
Use native Tkinter with a German four-tab workflow: folder/analysis, topic review,
per-file confirmation and processing history. Keep the three existing analysis modes.
Run analysis/network/copy work in background threads; pass UI updates through a queue.
Cancellation stops between safe steps and during the OAuth callback wait. Keep the
analysis/service layer separate from widgets. Check file hashes before and after
copying so changed inputs do not get deleted. Skip existing subfolders and Windows
reparse points. Credentials move to a stable, protected per-user AppData directory,
independent of the executable and selected PDF folder.

### Distribution
Package Python/Tcl/Tk and dependencies with PyInstaller; create a per-user Inno Setup
installer without administrator rights. Include third-party notices separately from
the project's rights notice. No code-signing certificate or repository PDFs. Build
on GitHub's Windows runner, run regressions and packaged startup checks, install into
an isolated build folder, verify the installed EXE, uninstall, and publish a candidate
release with an installer, portable ZIP, checksums and build metadata only on success.

### Validation status before CI
The 25 original tests and copy-verification regression run locally. Five new tests
that resolve Windows paths are blocked by the local sandbox's GetFinalPathName access
restriction. They are included in the Windows CI regression suite, not treated as
passing yet. GUI construction and installer checks run on the Windows runner. Live
ChatGPT eligibility and personal scholarly evaluation remain unverified.

### AI assistance
Codex drafted UI, service, packaging, documentation and regression tests. The owner
has not yet personally reviewed the desktop app. Packaging/CI results will be recorded
after the build; version 1.0.0 is a release candidate rather than a claim of production
readiness. CSV, OCR, embeddings and reference-manager adapters remain outside scope.

### Successful Windows build
The first Windows run passed 30/31 tests and exposed a test-path comparison between
Windows short and canonical path spellings. The assertion now uses the collection's
canonical folder. The service also preserves destinations of processed files and
invalidates old previews when the selected input folder or analysis mode changes.

Build 2 passed all 31 tests on Windows Server 2022 / Python 3.12.10, created the GUI
and captured its four pages with synthetic preview data, built the windowed EXE,
passed its dependency/DPAPI self-test and packaged Tk startup check, installed into
an isolated build directory, verified the installed EXE and uninstalled it successfully.
The public candidate `desktop-v1.0.0-build.2` contains an installer (17,534,744 bytes),
a portable ZIP (23,358,453 bytes), SHA256 checksums and source/build metadata.
Build source: `38326c9369235fe3dcb24910f71f8794fbed4c9f`.
Workflow: https://github.com/Antargos/SmartResearchArchive/actions/runs/38389684946
Release: https://github.com/Antargos/SmartResearchArchive/releases/tag/desktop-v1.0.0-build.2

The published EXE is unsigned. Real ChatGPT authorization, model quality, manual
usability testing and scholarly evaluation remain tasks for the owner. The build
does not authenticate as the user or send actual research PDFs to OpenAI.

## 3 November 2026 — Keep desktop actions reachable

User reported that PDFs analysieren was invisible even with the window maximized.
The form and notebook requested more height than available, and pack allocated the
bottom action after the form. Maximizing did not solve this at larger display scaling.

Use a weighted grid for the main notebook and reserve footer space. Add scrollable
page viewports and keep analysis, topic confirmation and per-file confirmation in
fixed action bars outside those viewports. Stack connection controls, shorten the
form's text wrapping, and allow 720×480 windows. Mouse-wheel handling is scoped to
the relevant page and preserves scrolling inside text/list widgets.

Version 1.0.1 adds real Windows Tk geometry checks at 100%, 150% and 200% scaling,
with 720×480, 800×500 and 1100×780 client windows. Checks require primary buttons
and cancel to fit inside every ancestor's visible bounds and verify that scrolling
the form does not move the analysis button. Build/installer checks remain enabled.
Codex drafted the fix and regression checks. CI results will determine release status;
this entry does not claim the user's display has already been tested personally.

### Validation and downloadable update
Windows build 3 passed the 31 existing regression tests and all three dedicated
real-Tk layout checks. Primary actions and cancel remained within visible ancestor
bounds in all nine size/scaling combinations, and page scrolling kept the analysis
button fixed. Packaged EXE startup, installation and uninstallation also passed.
Published update: https://github.com/Antargos/SmartResearchArchive/releases/tag/desktop-v1.0.1-build.3
Validated code: `96a7c81bc28082c090d8a1060a4a4bb4acd78f22`.
This is an automated reproduction of the size/scaling issue, not a personal test
on the user's monitor. Close the running app before installing version 1.0.1.

## 3 November 2026 — Delete saved ChatGPT connections

User requested removal of existing ChatGPT connections from the app. Version 1.0.2
adds Verbindung löschen next to the connection controls, with confirmation of the
selected account/workspace. Unlike sign-out, deletion forgets the entire local
registration and tokens. It attempts documented renewable-session revocation first,
preserves other registrations (including ones with the same email) and the host ID,
and clears the active pointer only if that registration was active. A missing
renewable session or failed revocation never prevents local deletion; failed remote
revocation is explicitly reported. A failed local write does not report success.

The remote registered app grant is not deleted by this endpoint; the UI explains
how to disconnect it in ChatGPT settings. Model choices are cleared after deletion,
and a pending semantic preview using that registration is invalidated. PDFs remain
untouched. Six isolated unit cases cover revocation, offline deletion, pending
records, identical email registrations, missing IDs, disk failure and endpoint
validation; a real Tk check covers confirmation cancellation and refreshed controls.
Tests use synthetic records only, without deleting the user's actual connections.
Codex drafted implementation, tests and documentation using official OpenAI Docs.

### Validation and update
Windows build 4 passed 37 non-GUI cases and four dedicated real-Tk cases, including
the confirmation-cancel/delete flow and cleared account/model controls. Packaged
startup, installation and uninstallation checks also passed. The release candidate
`desktop-v1.0.2-build.4` includes the updated installer and portable ZIP.
Validated code: `2424cabc8eec9f3ea04e944ae3490be77e243849`.
Release: https://github.com/Antargos/SmartResearchArchive/releases/tag/desktop-v1.0.2-build.4
These are simulated-account checks; the build did not revoke or delete any real
user connection. Runtime failure to confirm remote revocation is reported explicitly.

## 3 November 2026 — Isolate PDF evidence validation failures

The user supplied a log ending at PDF 1/22 with “Model evidence does not match the
PDF text; result rejected.” Earlier sign-in/out messages were separate attempts;
the final run had already received a model answer. The exact substring check
rejected layout-only differences as well as genuinely unsupported quotations, and
propagated both as a fatal collection-level ConnectionError.

Version 1.0.3 folds PDF whitespace, compatibility ligatures, soft hyphens and line-end
hyphenation for matching, while mapping a match back to an actual original source
substring. No fuzzy matching, translation or word substitution. Unmatched quotes
are discarded with warnings if another quote validates for the same section.
If any section has no valid evidence, reject that document's automatic analysis,
keep its metadata and mark it Unclassified for manual review. The rest of the
collection continues. Invalid per-document classification is similarly isolated.
Provider/network/auth/usage failures and incomplete streams remain fatal; no new
automatic inference retries. Apply the same isolation to desktop and CLI.

Codex drafted the fix after reviewing OpenAI Docs about validating model outputs.
Thirteen synthetic regressions cover formatting, unchanged source excerpts,
fabricated/transformed wording, partial-section rejection, continued collection
processing, per-PDF classification errors and stopping on genuine provider failures.
Ten text-only cases passed locally; the three PDF/folder cases require the Windows
runner because of local sandbox path/temp restrictions. The actual Jones PDF was
not provided, so this is not a reproduction using its copyrighted contents.

### Validation and release
Windows build 5 passed all 50 non-GUI cases (including all 13 new evidence cases)
and four dedicated Tk cases. EXE startup, install and uninstall checks passed.
Published `desktop-v1.0.3-build.5`, validated code
`ce2480a1d95fd74c145526600db9ff64a8ce739c`:
https://github.com/Antargos/SmartResearchArchive/releases/tag/desktop-v1.0.3-build.5
No real PDFs or user tokens were used in the build. The specific Jones document
remains untested; unsupported evidence still results in manual review, not acceptance.
