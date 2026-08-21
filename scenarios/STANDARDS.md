# Validation Standards — OPP Extraction Scenarios

This is the citable standards reference for the OPP extraction scenario
library under `Omni_Pre_Processor/scenarios/`. Every step that enforces a
quality bar cites the exact standard it checks as
`standard: STANDARDS.md#<anchor-id>`; the suite contract lint
(`run_validation.py --check`) resolves every citation against the
`### Name {#anchor}` headings below.

The bars follow the same two-family model as the suite-level
`scenarios/STANDARDS.md` — **AGENT-SURFACE** (agent-user conformance: the
`opp` CLI and `opp.mcp.server` tool registry behave as an agent-user
expects) and **HUMAN-QUALITY** (the extracted markdown/XLIFF intermediates
satisfy the downstream OL→ORF pipeline). Thresholds are copied verbatim
from shipped OPP behavior — never invented:

- The CLI success/failure contract (`commands/extract.py`, `cli.py`):
  exit 0 with no errors, exit 1 with the reason on stderr when a file
  fails or is missing (`cli.py:376`), and the `[INFO] Generated:` /
  `[INFO] Completed:` stderr markers the verbose logger emits.
- The XLIFF invariant (`src/opp/xliff/generator.py`, README "Output
  Files"): a produced `.xlf` is XLIFF 1.2, declares `source-language`
  / `target-language`, and carries at least one `<trans-unit>`.
- The manifest invariant (`commands/extract.py:223-268`): every
  extraction writes `<stem>_manifest.json` with `manifest_version`,
  `source.format`, and `extraction.outputs.{markdown,xliff}.path`.
- The JSON extractor structure (`extractors/json.py`, CHANGELOG 0.7.0):
  a JSON input produces a ` ```json ` fenced block preserving the full
  payload plus `json_field:path = value` lines for translation.

## AGENT-SURFACE

Mission axis 1: validation proves every agent-facing OPP surface — the
`opp` console script and the live `opp.mcp.server` tool registry — works
as an agent-user would use it: schema-shaped parameters accepted,
structured results returned, clear parseable errors on bad input, sane
exit codes, and a structured success marker an agent can branch on.

### Tool contract conformance {#tool-contract}

Every OPP tool accepts its schema-shaped parameters, executes against the
real surface (the `opp` console script, or the in-process
`opp.mcp.server.<tool>` function after `_init_server(load_config())` —
the exact initialization `opp mcp` performs), and returns a structured
result carrying the expected keys. A step enforces this with an `expect`
block of `exit_code: 0` plus stream/JSON assertions naming the keys the
live surface returns.

**How to check:** run the real CLI with `-v` and assert `exit_code: 0`
plus `stderr_has: ["[INFO] Generated:"]`; or drive the in-process tool
function and assert `success: true` plus the payload keys. Citable as
`standard: STANDARDS.md#tool-contract`.

### JSON parseability {#json-parseable}

Every manifest file OPP writes and every structured tool payload parses
as valid JSON — an agent-user's `json.loads` must never fail on the
suite's own output. A response that cannot be parsed is a contract break
regardless of content.

**How to check:** `json.loads` on the produced `*_manifest.json` inside a
python step; a `JSONDecodeError` fails the step. Also assert the
`source.format` value matches the input's detected format. Citable as
`standard: STANDARDS.md#json-parseable`.

### Error clarity {#error-clarity}

Failures are reported as clear, parseable, agent-readable errors that
name the failing file — never raw stack-trace soup. The CLI prints the
reason to stderr and exits nonzero (`commands/extract.py:303-309`,
`cli.py:376`); the MCP error boundary returns a `{success: false,
error: {code, message}}` payload with a stable `error_code`
(`opp/mcp/_errors.py`). An agent must be able to act on the message
without reading the engine source.

**How to check:** invoke the surface with a missing input; expect a
nonzero exit and the failure reason on stderr (CLI), or a
`"success": false` payload naming the path (MCP) — and in both cases no
`Traceback (most recent call last)` frame. Citable as
`standard: STANDARDS.md#error-clarity`.

### Path security {#path-security}

Path-taking MCP tools deny access outside the configured allowlist
(`MCP_ALLOWED_DIRECTORIES` / `OPP_MCP_ALLOWED_DIRS`); an out-of-allowlist
path MUST be rejected with a clear denial, never silently accepted. OPP
is fail-closed — an unset allowlist means the server refuses to start
(`config.py:172-173`).

**How to check:** call a path-taking tool with a path outside the
declared allowlist; expect a denial (`success: false` / `OPP_PATH_DENIED`
in the payload) naming the path, no traceback. Citable as
`standard: STANDARDS.md#path-security`.

### Exit codes {#exit-codes}

CLI commands exit 0 on success and a nonzero code on failure, with the
failure reason on stderr — so scripts and agents can branch on the code
(`cli.py:376` `return 0 if stats["errors"] == 0 else 1`). Missing or
unsupported inputs surface as exit 1 with a clear stderr warning, never
as a crash.

**How to check:** `expect: {exit_code: 0}` on success paths;
`expect: {exit_code: 1, stderr_has: [...]}` on failure paths. Citable as
`standard: STANDARDS.md#exit-codes`.

## HUMAN-QUALITY

Mission axis 2: a green OPP run must prove the extracted intermediates
(Markdown + XLIFF) are usable by the downstream OL → ORF pipeline —
content preserved, structure intact, and a translation-ready XLIFF
carrying the declared language pair.

### XLIFF translation-readiness {#xliff-trans-ready}

A produced `.xlf` must be XLIFF 1.2 XML: it declares the source and
target languages on the `<file>` element and carries at least one
`<trans-unit>` with a non-empty `<source>` (the unit OL will translate).
This is the OPP prep contract that makes `ol translate-xliff` →
`orf apply-xliff` possible.

**How to check:** read the produced `.xlf`; assert `source-language="en"`
and `target-language="zh"` are declared, `<trans-unit` occurs at least
once, and every `<source>` is non-empty. Citable as
`standard: STANDARDS.md#xliff-trans-ready`.

### Markdown content preservation {#md-content}

The extracted `.md` must preserve the source content — the payload
survives in a recognizable structure (a ` ```json ` fenced block for JSON
inputs per `extractors/json.py`, headings/paragraphs for HTML inputs), so
the markdown is a faithful intermediate for `ol translate-md`. A
zero-content or structurally-empty `.md` fails regardless of exit code.

**How to check:** read the produced `.md` and assert distinctive source
substrings survive inside the expected structure (e.g. ` ```json ` +
payload tokens for JSON, `# ` heading for HTML). Citable as
`standard: STANDARDS.md#md-content`.

### Manifest fidelity {#manifest-fidelity}

Every extraction writes `<stem>_manifest.json` whose `extraction.outputs`
correctly names the produced files — `markdown.path` and `xliff.path`
must match what actually landed in the output directory. The manifest is
what ORF's manifest parser and the director's artifact review rely on, so
a manifest that lies about output paths fails.

**How to check:** after the extraction step, `json.loads` the manifest,
assert `manifest_version` and `source.format`, and assert
`extraction.outputs.markdown.path` equals the real file name on disk
(asserted via `collect_artifacts` / a `pathlib.Path.exists()` check).
Citable as `standard: STANDARDS.md#manifest-fidelity`.

## Reference: OPP surface facts

Not bars — the structural facts scenario steps cite from the shipped OPP
source.

- **CLI console script**: `opp` (`.venv_ol/bin/opp`), argparse. On
  success with `-v`, stderr carries `[INFO] Generated: <path>` per output
  file and `[INFO] Completed: N succeeded, M failed`; exit 0 when `errors
  == 0`, else 1 (`cli.py:376`).
- **`--target-format`**: `md` | `xlf` | `both` | `html`; `xlf`/`both`
  require `--target-lang` (`cli.py:259-260`). For `both`, OPP writes
  `<stem>.md` + `<stem>.xlf` (+ `<stem>.html` for HTML input) +
  `<stem>_manifest.json`.
- **Magic-byte detection** (`detector.py`): JSON inputs (first byte `{`
  or `[`) and HTML inputs (`<!doctype html` / `<html`) detect with
  confidence 1.0 regardless of extension. `.txt` has no extractor — it
  detects as `unknown` and the CLI exits 1.
- **MCP tools** (`opp.mcp.server`): `ping`, `detect_format_tool`,
  `extract_document`, `batch_extract`, `generate_markdown`,
  `generate_xliff`, `save_skeleton`, `validate_xliff`,
  `get_capabilities`. All require `_init_server(load_config())` and an
  allowlist set (`OPP_MCP_ALLOWED_DIRS` / `MCP_ALLOWED_DIRECTORIES`).
  Errors return `{success: false, error: {code, message}, error_code}`
  via the `@mcp_error_boundary` decorator (`opp/mcp/_errors.py`).
- **Hermeticity**: JSON and HTML inputs need no pandoc, no OCR, no
  network, no LLM keys — the tier-1-safe formats this library uses.
