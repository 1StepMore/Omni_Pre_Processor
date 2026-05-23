# Agent-Facing MCP - Task 12 Security Tests - Learnings

## Completed
- Created `tests/mcp/test_security.py` with comprehensive security tests for `PathValidator`
- Test coverage includes:
  - Path traversal blocking (5 parametrized cases)
  - System directory blocking (/etc, /usr, /var, /System, /Library, C:\Windows)
  - Symlink resolution and blocking (including cross-directory symlinks)
  - Executable extension blocking (.exe, .bat, .cmd, .sh, .ps1, .vbs, .js)
  - File size limit enforcement (default 100MB, custom limits)
  - File existence and type validation
  - Multiple allowed directories support
  - Invalid path format handling
  - Case-insensitive extension checking
  - ValidationResult dataclass

## Test Results
- 35 passed, 5 skipped (skipped tests are Unix-specific system directories on Linux)

## Key Patterns Found
- Tests use `importlib.util.spec_from_file_location` to dynamically import modules
- `pytest.mark.parametrize` used for multiple test cases
- `pytest.mark.skipif(os.name != "nt")` for platform-specific tests
- `tmp_path` fixture used for creating temporary test files
- Fixtures nested under `tmp_path/allowed` to ensure proper directory isolation
- Symlink tests need to create symlink in allowed dir pointing to outside target

## Issues Encountered
- Windows path checking on Unix: `C:\Windows` paths resolve to `/tmp/...` on Unix, so test validates the error comes from "not within allowed directories" rather than "system directory"
- tmp_path is a pytest fixture and already nested - if validator uses tmp_path directly, files created there are within allowed_dir. Solution: use `tmp_path / "allowed"` as the actual allowed_dir
- Symlink tests: symlink path must be in the allowed dir, but target must be outside
---

## Task 17: OpenCode SKILL.md for OPP - Completed

### Completed
- Created `src/opp_agent/SKILL.md` with valid frontmatter (YAML parses correctly)
- Created `src/opp_agent/__init__.py` (empty package init)
- SKILL.md contains:
  - `name: opp-extract` in frontmatter
  - Full description of document formats supported
  - MCP server configuration using `uvx opp-mcp-server`
  - Environment variables: OPP_MCP_ALLOWED_DIRS="${workspace_dir}", OPP_MCP_MAX_FILE_SIZE="100000000"
  - "When to Use This Skill" section with 7 use cases
  - "Tools Available" section listing all 5 tools
  - "Usage Examples" section with 3 code examples
  - "Security" section with 4 security notes

### Key Patterns Found
- OpenCode SKILL.md uses YAML frontmatter with `name`, `description`, and `mcp` sections
- MCP server env vars are passed via the `env` key in the mcp configuration
- `${workspace_dir}` is the correct placeholder for dynamic workspace directory path
- SKILL.md content after frontmatter uses standard markdown format

### Files Created
- `src/opp_agent/SKILL.md` (53 lines, 1629 bytes)
- `src/opp_agent/__init__.py` (0 bytes - empty init)

### Verification
- Frontmatter parses as valid YAML via `yaml.safe_load()`
- `name: opp-extract` confirmed present
- `command: uvx` confirmed in MCP config
- Environment variables correctly set
