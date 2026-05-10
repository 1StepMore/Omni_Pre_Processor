# TestPyPI Publishing Verification Guide

## Overview

This document explains how to test the GitHub Actions publishing workflow to TestPyPI and verify the package before promoting to production PyPI.

---

## 1. How to Test the Publishing Workflow

### Prerequisites

1. Ensure `src/opp/__init__.py` has the correct version matching your planned release
2. Ensure you're on a clean branch with all changes committed

### Version Bump Instructions

**Important:** The workflow requires semantic versioning format (`X.Y.Z`) - alpha versions like `0.1.1a0` will FAIL validation.

1. **Update version in source:**
   ```bash
   # Edit src/opp/__init__.py
   __version__ = "0.1.0"  # or your test version
   ```

2. **Commit the version bump:**
   ```bash
   git add src/opp/__init__.py
   git commit -m "Bump version to 0.1.0 for TestPyPI test"
   ```

3. **Create git tag:**
   ```bash
   git tag v0.1.0
   ```

4. **Push tag to trigger workflow:**
   ```bash
   git push origin v0.1.0
   ```

5. **Monitor GitHub Actions:**
   - Go to: https://github.com/<owner>/<repo>/actions
   - Watch the "Publish" workflow run
   - The workflow runs: Test → Verify Version → Build → Publish to TestPyPI

### Expected Workflow Stages

| Stage | Status | Description |
|-------|--------|-------------|
| Test | Runs pytest | Verifies code integrity |
| Verify Version | Checks tag matches source | Ensures consistency |
| Build | Creates dist/ package | Builds sdist and wheel |
| Publish to TestPyPI | Uploads to test.pypi.org | Makes package available |

---

## 2. What to Verify After TestPyPI Publish

### Step 1: Check Package on TestPyPI

1. Navigate to: https://test.pypi.org/project/opp/
2. Verify:
   - Package name is `opp`
   - Version matches your tag (e.g., `0.1.0`)
   - Files are present (tarball + wheel)

### Step 2: Test Package Installation

```bash
# Create fresh virtual environment
python -m venv test_install
source test_install/bin/activate

# Install from TestPyPI (not production!)
pip install --index-url https://test.pypi.org/simple/ opp
```

### Step 3: Verify Import Works

```bash
python -c "import opp; print(opp.__version__)"
```

Expected output: `0.1.0` (or your test version)

### Step 4: Smoke Test Basic Functionality

```bash
python -c "
from opp import DOCXExtractor, PDFExtractor, PPTXExtractor
from opp.detector import detect_format
print('All imports successful')
"
```

### Verification Checklist

- [ ] Package appears on https://test.pypi.org/project/opp/
- [ ] Correct version number displayed
- [ ] `pip install --index-url https://test.pypi.org/simple/ opp` succeeds
- [ ] `import opp` works without errors
- [ ] `opp.__version__` returns expected version
- [ ] Basic imports (DOCXExtractor, PDFExtractor, etc.) work

---

## 3. How to Promote to Production PyPI

### After TestPyPI Verification

1. **Clean up test version:**
   ```bash
   # Revert version bump or update to production version
   # Edit src/opp/__init__.py with production version
   __version__ = "1.0.0"  # or actual release version
   ```

2. **Commit production version:**
   ```bash
   git add src/opp/__init__.py
   git commit -m "Release v1.0.0"
   ```

3. **Create production tag:**
   ```bash
   git tag v1.0.0
   ```

4. **Push to trigger TestPyPI workflow:**
   ```bash
   git push origin v1.0.0
   ```

5. **Wait for TestPyPI publish to complete**, then verify again

6. **Trigger PyPI publish manually:**
   - Go to: https://github.com/<owner>/<repo>/actions/workflows/publish.yml
   - Click "Run workflow"
   - Select the tag (e.g., `v1.0.0`)
   - The `publish-pypi` job requires `workflow_dispatch` and only runs after TestPyPI success

### Alternative: Manual Workflow Dispatch with Version Input

The workflow also accepts a version input for direct publishing:

1. Go to: https://github.com/<owner>/<repo>/actions/workflows/publish.yml
2. Click "Run workflow"
3. Enter the version number (e.g., `1.0.0`)
4. This will build and publish directly (bypassing tag requirement)

---

## Important Notes

### DO NOT
- ❌ Push tags with test versions to main/production branches
- ❌ Leave test versions (like `0.1.1a0`) in the codebase
- ❌ Manually trigger PyPI publish without verifying TestPyPI first

### DO
- ✅ Always test with TestPyPI first
- ✅ Verify installation from TestPyPI before production
- ✅ Clean up test artifacts after verification
- ✅ Use semantic versioning for production releases

---

## Troubleshooting

### "Version does not match" Error
- Ensure `src/opp/__init__.py` version exactly matches the tag version
- Tag: `v0.1.0` → Source: `__version__ = "0.1.0"`

### "Invalid version format" Error
- Only semantic versions (`X.Y.Z`) are accepted
- No alpha (`a0`), beta (`b1`), or rc (`rc1`) suffixes
- Use format: `0.1.0`, `1.0.0`, etc.

### Package Not Appearing on TestPyPI
- Check GitHub Actions logs for errors
- Verify `testpypi` environment is properly configured
- Check that `pypa/gh-action-pypi-publish` has valid TestPyPI credentials

---

## Workflow Summary

```
[Tag Push] → Test → Verify Version → Build → TestPyPI Publish
                                                    ↓
                              [Manual Trigger] ← Publish to PyPI
```

The production PyPI publish is intentionally a separate manual step to ensure verification occurs first.