# OPP --target-format Selection Guide (moved from AGENTS.md, OPP#119)

Choose `--target-format` based on your downstream pipeline:

| Flag | Produces | Downstream | Best for |
|------|----------|------------|----------|
| `md` | `.md` file | OL `translate-md` → ORF `apply-md` | Fast text output, 16 output formats |
| `xlf` | `.xlf` + `skeleton.zip` | OL `translate-xliff` → ORF `apply-xliff` | Original layout preservation |
| `both` | `.md` + `.xlf` + `skeleton.zip` | Either path | Maximum flexibility |

**Decision flow:**

1. Need clean text fast, or converting to a different format? → **`md`**
2. Need the output to look exactly like the source? → **`xlf`** (requires skeleton.zip)
3. Not sure yet? → **`both`** (costs extra extraction time, but keeps options open)

**Caveats:**
- PDF → XLIFF is intentionally blocked (see [PDF / XLIFF limitation](xliff-schema.md#pdf--xliff-limitation))
- skeleton.zip is produced for DOCX/PPTX/EPUB/HTML/XLSX inputs; EML and the
  data formats have none (see [Skeleton preservation](skeleton.md))
- `both` runs MD generation + XLIFF generation, roughly doubling extraction time

**Full pipeline comparison**: See the suite-level
[Pipeline Selection Strategy](https://github.com/1StepMore/e2e-test-suite/blob/main/README.md#pipeline-selection-strategy)
for the complete decision tree and format support matrix.