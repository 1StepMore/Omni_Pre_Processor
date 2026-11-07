# OPP module validation (moved from AGENTS.md, OPP#119)

OPP ships its own validation scenario library **in this repo** at
`scenarios/` — 6 tier-1 `opp-extraction` scenarios (format detection, CLI
extraction, JSON→XLIFF regression, MCP tool calls, error handling) with
their own `scenarios/STANDARDS.md` + `scenarios/_fixtures/`. The suite
validation engine runs them via `--repo opp`. The suite's own
`tool-opp-*` agent-surface scenarios (MCP tool contracts) still live in
the suite repo and are covered by the suite-level `--module opp` filter.
Any agent or the human director can validate OPP in isolation:

```bash
# From the Omni Suite root (clone: https://github.com/1StepMore/e2e-test-suite)
source .venv_ol/bin/activate

# List OPP's in-repo scenarios
python scripts/validation/run_validation.py --repo opp --list

# Run OPP's in-repo hermetic scenarios (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --repo opp --tier 1

# Or use the suite-level module filter (adds tool-opp-* agent-surface scenarios)
python scripts/validation/run_validation.py --module opp --tier 1

# Coverage: every OPP MCP tool must be scenario-exercised
python scripts/validation/coverage_audit.py   # opp row must show 9/9, 0 missing
```

The standards bar is `scenarios/STANDARDS.md` (AGENT-SURFACE family:
tool-contract, json-parseable, error-clarity, path-security, exit-codes).
Director loop + 10-minute checklist: `docs/dev/validation-director-loop.md`
in the suite repo. Per-repo validation delivery (run_meta, report card,
delivery package): `docs/dev/per-repo-validation-delivery.md`. OPP
scenario fixes now live HERE (in `scenarios/`); OPP product-code fixes
go through the normal fix cycle in this repo.