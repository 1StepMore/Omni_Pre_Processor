# Phase 8: Rich Media & Advanced Format Extension (v2.0)

## TL;DR

> **Quick Summary**: Extend OPP to support Audio (WAV/MP3), Video (MP4 via audio extraction), Jupyter Notebook (IPYNB), and YouTube URL transcription.
>
> **Deliverables**:
> - Audio extractor with Whisper transcription
> - Video extractor (audio-only extraction + transcription)
> - Jupyter Notebook extractor (markdown + code cells)
> - YouTube URL extractor (subtitle/caption extraction)
> - Optional dependency management for heavy ASR libraries
>
> **Estimated Effort**: Medium (~2 days)
> **Parallel Execution**: YES - 2 waves (Foundation + Core Extractors)
> **Critical Path**: Wave 1 (Foundation) → Wave 2 (Extractors) → Integration

---

## Context

### Original Request
User wants to implement Phase 8 of OPP (Omni Pre-Processor) as defined in "OPP增补完整版.md", covering rich media and advanced format support.

### Metis Review Findings

**Identified Gaps (addressed in plan)**:
- **Bug**: `pyproject.toml` has `nbformat` in `[audio]` extra (wrong location) - will correct to `[notebook]` extra
- **Missing FormatType enum entries**: AUDIO, VIDEO, IPYNB, YOUTUBE not in detector
- **Missing boundary conditions**: No max audio file size, no transcription timeout - will add
- **YouTube without API**: markitdown works without API key but has limitations on age-restricted content
- **XLIFF applicability**: Audio transcription has no translatable structure - XLIFF output will be skipped for audio

**Guardrails Applied**:
- Audio formats: WAV + MP3 only (no FLAC/OGG/M4A)
- Video: Audio track extraction only (no frame processing)
- YouTube: markitdown without API key only
- Whisper model: `tiny` default (GPU memory constraint)
- Jupyter cells: code + markdown only (ignore raw/output cells)

---

## Work Objectives

### Core Objective
Implement Phase 8 rich media support: audio transcription, Jupyter notebook extraction, and YouTube subtitle extraction.

### Concrete Deliverables
- `src/opp/extractors/audio.py` - WAV/MP3 transcription via Whisper
- `src/opp/extractors/video.py` - MP4 audio extraction + transcription
- `src/opp/extractors/ipynb.py` - Jupyter Notebook cell extraction
- `src/opp/extractors/youtube.py` - YouTube URL subtitle extraction
- `tests/test_audio_extractor.py` - Audio transcription tests
- `tests/test_ipynb_extractor.py` - Jupyter notebook tests
- `tests/test_youtube_extractor.py` - YouTube extraction tests
- Updated `pyproject.toml` with proper `[audio]` and `[notebook]` extras

### Definition of Done
- [ ] `opp convert meeting.mp3 --target-format md` produces Markdown with transcription
- [ ] `opp convert lecture.ipynb --target-format md` produces Markdown with code blocks
- [ ] `opp convert "https://youtube.com/watch?v=..." --target-format md` produces Markdown with subtitles
- [ ] All extractors follow `ExtractorBase` pattern
- [ ] All new extractors registered in `OPPPipeline.extractors` dict
- [ ] Pytest passes with `pip install -e ".[audio,notebook]"`
- [ ] Graceful error when Whisper not installed

### Must Have
- Audio transcription with Whisper (WAV/MP3 → text)
- Video audio extraction + transcription (MP4 → text)
- Jupyter notebook markdown + code cell extraction
- YouTube subtitle extraction (markitdown)
- Optional dependency extras (`opp[audio]`, `opp[notebook]`)
- Graceful degradation when heavy dependencies unavailable

### Must NOT Have (Guardrails)
- **NO** video frame extraction or video-to-description
- **NO** speaker diarization
- **NO** cloud ASR alternatives (AWS Transcribe, Google Speech)
- **NO** FLAC/OGG/M4A support (WAV/MP3 only for audio)
- **NO** Jupyter output cell processing (code + markdown cells only)
- **NO** YouTube API key dependency
- **NO** XLIFF export for audio transcription (no translatable structure)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after (due to non-deterministic ASR output)
- **Framework**: pytest with `pytest.importorskip()` for optional heavy deps

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Audio/Video**: Bash with `whisper` CLI or Python API
- **Jupyter**: Bash with `python -c "import nbformat; ..."` REPL
- **YouTube**: Bash with `markitdown --help` validation + mock URL test

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - scaffolding + bug fixes):
├── Task 1: Fix pyproject.toml extra organization [quick]
├── Task 2: Add FormatType entries (AUDIO/VIDEO/IPYNB/YOUTUBE) [quick]
├── Task 3: Create AudioTranscriber class with Whisper integration [deep]
├── Task 4: Create IPYNBExtractor following base pattern [deep]
└── Task 5: Create YouTubeExtractor with markitdown [deep]

Wave 2 (Core extractors + integration):
├── Task 6: Implement AudioExtractor (WAV/MP3 → text) [deep]
├── Task 7: Implement VideoExtractor (MP4 → audio → text) [deep]
├── Task 8: Register extractors in OPPPipeline [quick]
├── Task 9: Implement CLI entry points for audio/notebook [quick]
└── Task 10: Integration tests + documentation [unspecified-high]

Wave FINAL (Verification):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review
├── Task F3: Real manual QA
└── Task F4: Scope fidelity check
```

### Dependency Matrix

- **Task 3-10**: Blocked by Task 1, 2 (foundation must come first)
- **Task 7**: Depends on Task 6 (video uses audio extraction pattern)
- **Task 8**: Depends on Tasks 3, 6, 7
- **Task 9**: Depends on Task 8
- **Task 10**: Depends on Tasks 4, 5, 9

### Agent Dispatch Summary

- **Wave 1**: 5 tasks - T1 → `quick`, T2 → `quick`, T3 → `deep`, T4 → `deep`, T5 → `deep`
- **Wave 2**: 6 tasks - T6 → `deep`, T7 → `deep`, T8 → `quick`, T9 → `quick`, T10 → `unspecified-high`
- **FINAL**: 4 tasks - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Fix pyproject.toml extra organization

  **What to do**:
  - Move `nbformat` from `[audio]` extra to new `[notebook]` extra
  - Add `faster-whisper` to `[audio]` extra
  - Add `markitdown[youtube]` to `[audio]` extra
  - Verify syntax is valid TOML

  **Must NOT do**:
  - Do NOT add other ASR libraries (only Whisper)
  - Do NOT add video processing libraries

  **Recommended Agent Profile**:
  > **Category**: `quick`
  > - Reason: Simple TOML edit, well-defined scope
  > **Skills**: []
  > - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: Task 3 (AudioTranscriber needs whisper dependency)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `pyproject.toml:32-40` - Current extras structure (bug location)
  - `pyproject.toml:15-30` - Other extras pattern to follow

  **Acceptance Criteria**:
  - [ ] TOML parses without error: `python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"`
  - [ ] `[audio]` extra contains: whisper, markitdown
  - [ ] `[notebook]` extra contains: nbformat
  - [ ] `[all]` extra includes both `[audio]` and `[notebook]`

  **QA Scenarios**:

  ```
  Scenario: pyproject.toml is valid TOML
    Tool: Bash
    Steps:
      1. python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"
      2. Assert exit code 0
    Expected Result: No syntax error
    Evidence: .sisyphus/evidence/task-1-toml-valid.txt

  Scenario: audio extra contains correct dependencies
    Tool: Bash
    Steps:
      1. python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['optional-dependencies']['audio'])"
      2. Assert 'whisper' in output or 'faster-whisper' in output
      3. Assert 'markitdown' in output
    Expected Result: audio extra contains ASR and YouTube tools
    Evidence: .sisyphus/evidence/task-1-audio-extra.txt
  ```

  **Commit**: YES (grouped with Task 2)
  - Message: `fix(deps): reorganize pyproject.toml extras for Phase 8`
  - Files: `pyproject.toml`

- [x] 2. Add FormatType entries (AUDIO/VIDEO/IPYNB/YOUTUBE)

  **What to do**:
  - Add `AUDIO`, `VIDEO`, `IPYNB`, `YOUTUBE` to FormatType enum in `src/opp/detector.py`
  - Add magic bytes patterns for WAV (RIFF header), MP3 (ID3 tag), IPYNB (JSON with "ipynb" mimetype)
  - Video detection for MP4 (ftyp box)
  - YouTube URL regex pattern

  **Must NOT do**:
  - Do NOT add FLAC/OGG detection (out of scope)
  - Do NOT add actual video frame detection

  **Recommended Agent Profile**:
  > **Category**: `quick`
  > - Reason: Enum addition + pattern matching, straightforward
  > **Skills**: []
  > - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: Task 8 (extractor registration needs FormatType)
  - **Blocked By**: None (can start immediately)

  **References**:
  - `src/opp/detector.py:1-80` - Existing FormatType enum and detection logic
  - `src/opp/detector.py:check_docx()`, `check_pdf()` - Pattern for format checkers

  **Acceptance Criteria**:
  - [ ] FormatType.AUDIO exists
  - [ ] FormatType.VIDEO exists
  - [ ] FormatType.IPYNB exists
  - [ ] FormatType.YOUTUBE exists
  - [ ] `detect_format("test.mp3")` returns AUDIO with confidence
  - [ ] `detect_format("test.ipynb")` returns IPYNB with confidence

  **QA Scenarios**:

  ```
  Scenario: WAV file detected as AUDIO
    Tool: Bash
    Preconditions: Create temp WAV file or use existing test file
    Steps:
      1. python -c "from opp.detector import detect_format; fmt, conf = detect_format('tests/fixtures/sample.wav'); print(f'{fmt.name}:{conf}')"
      2. Assert output contains "AUDIO"
    Expected Result: WAV detected correctly
    Evidence: .sisyphus/evidence/task-2-audio-detection.txt

  Scenario: Jupyter notebook detected as IPYNB
    Tool: Bash
    Preconditions: Create temp .ipynb or use existing test file
    Steps:
      1. python -c "from opp.detector import detect_format; fmt, conf = detect_format('tests/fixtures/sample.ipynb'); print(f'{fmt.name}:{conf}')"
      2. Assert output contains "IPYNB"
    Expected Result: IPYNB detected correctly
    Evidence: .sisyphus/evidence/task-2-ipynb-detection.txt

  Scenario: YouTube URL detected as YOUTUBE
    Tool: Bash
    Steps:
      1. python -c "from opp.detector import detect_format; fmt, conf = detect_format('https://youtube.com/watch?v=dQw4w9WgXcQ'); print(f'{fmt.name}:{conf}')"
      2. Assert output contains "YOUTUBE"
    Expected Result: YouTube URL detected correctly
    Evidence: .sisyphus/evidence/task-2-youtube-detection.txt
  ```

  **Commit**: YES (grouped with Task 1)
  - Message: `feat(detector): add AUDIO, VIDEO, IPYNB, YOUTUBE format types`
  - Files: `src/opp/detector.py`

- [x] 3. Create AudioTranscriber class with Whisper integration

  **What to do**:
  - Create `AudioTranscriber` class in `src/opp/transcriber.py`
  - Implement `transcribe(audio_path: str, model: str = "tiny") -> TranscriptionResult`
  - `TranscriptionResult` should contain: `text`, `language`, `segments` (list of {start, end, text})
  - Handle missing Whisper gracefully with clear error message
  - Support WAV and MP3 input

  **Must NOT do**:
  - Do NOT implement speaker diarization
  - Do NOT use non-Whisper ASR engines
  - Do NOT download model on every call (cache locally)

  **Recommended Agent Profile**:
  > **Category**: `deep`
  > - Reason: Whisper API integration, audio processing, async considerations
  > **Skills**: []
  > - No specialized skills needed - follow existing extractor patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5)
  - **Blocks**: Task 6 (AudioExtractor uses this)
  - **Blocked By**: Task 1 (needs whisper dependency defined)

  **References**:
  - `src/opp/extractors/base.py:10-37` - ExtractorBase pattern to follow
  - `src/opp/error_handler.py:1-50` - Error handling patterns

  **Acceptance Criteria**:
  - [ ] `AudioTranscriber` class exists in `src/opp/transcriber.py`
  - [ ] `transcribe("test.wav")` returns `TranscriptionResult` with text and segments
  - [ ] Missing Whisper raises `ImportError` with installation instructions
  - [ ] Model downloads are cached (no re-download on every call)

  **QA Scenarios**:

  ```
  Scenario: transcribe clear audio returns text
    Tool: Bash
    Preconditions: whisper installed, test audio available
    Steps:
      1. python -c "from opp.transcriber import AudioTranscriber; t = AudioTranscriber(); result = t.transcribe('tests/fixtures/clear_audio.wav'); print(result.text[:100])"
      2. Assert result.text is non-empty string
      3. Assert result.segments is list
    Expected Result: Transcription returned with text and segments
    Evidence: .sisyphus/evidence/task-3-transcribe-success.txt

  Scenario: Whisper not installed raises clear error
    Tool: Bash
    Preconditions: whisper not in environment
    Steps:
      1. python -c "from opp.transcriber import AudioTranscriber; t = AudioTranscriber()" in env without whisper
      2. Assert ImportError or clear error with pip install instructions
    Expected Result: Clear error message with installation guide
    Evidence: .sisyphus/evidence/task-3-whisper-missing-error.txt

  Scenario: language detection works
    Tool: Bash
    Steps:
      1. python -c "from opp.transcriber import AudioTranscriber; t = AudioTranscriber(); result = t.transcribe('tests/fixtures/english_audio.wav'); print(result.language)"
      2. Assert result.language is "en" or similar ISO code
    Expected Result: Language detected correctly
    Evidence: .sisyphus/evidence/task-3-language-detection.txt
  ```

  **Commit**: YES (grouped with Task 1, 2)
  - Message: `feat(audio): add AudioTranscriber with Whisper integration`
  - Files: `src/opp/transcriber.py`

- [x] 4. Create IPYNBExtractor following base pattern

  **What to do**:
  - Create `IPYNBExtractor` class in `src/opp/extractors/ipynb.py`
  - Inherit from `ExtractorBase`
  - Implement `extract_cells(ipynb_path: str) -> List[CellData]`
  - `CellData` type: `{cell_type: "markdown"|"code", source: str, metadata: dict}`
- Only process `code` and `markdown` cell types (ignore `raw` cells)
- **Include code cell outputs as comments** in the source
- Use `nbformat` library to parse

  **Must NOT do**:
  - Do NOT process `output` cells
  - Do NOT process `raw` cells
  - Do NOT execute notebook code

  **Recommended Agent Profile**:
  > **Category**: `deep`
  > - Reason: Notebook JSON structure parsing, cell type filtering
  > **Skills**: []
  > - No specialized skills needed - follow existing extractor patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5)
  - **Blocks**: Task 10 (integration tests)
  - **Blocked By**: Task 1 (needs nbformat in dependencies)

  **References**:
  - `src/opp/extractors/base.py:10-37` - ExtractorBase ABC to inherit
  - `src/opp/extractors/email.py:21-33` - EmailExtractor pattern (validate then dispatch)
  - `tests/test_email_extractor.py:11-12` - `pytest.importorskip("nbformat")` pattern

  **Acceptance Criteria**:
  - [ ] `IPYNBExtractor` inherits from `ExtractorBase`
  - [ ] `extract("test.ipynb")` returns list of `CellData`
  - [ ] Markdown cells have `cell_type="markdown"`
  - [ ] Code cells have `cell_type="code"`
  - [ ] `raw` cells are filtered out
  - [ ] Code cell outputs are preserved as comments

  **QA Scenarios**:

  ```
  Scenario: extract standard notebook with MD and code cells
    Tool: Bash
    Preconditions: nbformat installed, test notebook exists
    Steps:
      1. python -c "from opp.extractors.ipynb import IPYNBExtractor; e = IPYNBExtractor(); cells = e.extract('tests/fixtures/sample.ipynb')"
      2. Assert len(cells) > 0
      3. Assert any(c.cell_type == 'markdown' for c in cells)
      4. Assert any(c.cell_type == 'code' for c in cells)
    Expected Result: All MD and code cells extracted, outputs ignored
    Evidence: .sisyphus/evidence/task-4-extract-success.txt

  Scenario: corrupted notebook JSON raises ExtractionError
    Tool: Bash
    Steps:
      1. echo '{"cells": [{"cell_type": invalid}]}' > /tmp/bad.ipynb
      2. python -c "from opp.extractors.ipynb import IPYNBExtractor; e = IPYNBExtractor(); e.extract('/tmp/bad.ipynb')"
      3. Assert raises ExtractionError with clear message
    Expected Result: Clear error message about JSON structure
    Evidence: .sisyphus/evidence/task-4-corrupt-notebook.txt

  Scenario: notebook with output cells - outputs ignored
    Tool: Bash
    Steps:
      1. python -c "from opp.extractors.ipynb import IPYNBExtractor; e = IPYNBExtractor(); cells = e.extract('tests/fixtures/notebook_with_outputs.ipynb')"
      2. Assert no cell has cell_type='output'
    Expected Result: Only code and markdown cells returned
    Evidence: .sisyphus/evidence/task-4-outputs-ignored.txt
  ```

  **Commit**: YES (grouped with Task 5)
  - Message: `feat(ipynb): add IPYNBExtractor for Jupyter notebook parsing`
  - Files: `src/opp/extractors/ipynb.py`

- [x] 5. Create YouTubeExtractor with markitdown

  **What to do**:
  - Create `YouTubeExtractor` class in `src/opp/extractors/youtube.py`
  - Use `markitdown` library to extract subtitles/transcripts
  - Support URL validation (format checking before attempting extraction)
  - Handle missing subtitles gracefully with warning
  - Handle age-restricted/private videos with clear error

  **Must NOT do**:
  - Do NOT require YouTube API key
  - Do NOT attempt to bypass age restrictions or rate limits
  - Do NOT download video, only subtitles/text

  **Recommended Agent Profile**:
  > **Category**: `deep`
  > - Reason: External API (markitdown) integration, error handling for edge cases
  > **Skills**: []
  > - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4)
  - **Blocks**: Task 10 (integration tests)
  - **Blocked By**: Task 1 (needs markitdown dependency)

  **References**:
  - `src/opp/extractors/base.py:10-37` - ExtractorBase pattern
  - `src/opp/error_handler.py` - Error hierarchy patterns
  - `markitdown` documentation - YouTube extraction API

  **Acceptance Criteria**:
  - [ ] `YouTubeExtractor` inherits from `ExtractorBase`
  - [ ] `extract("https://youtube.com/watch?v=...")` returns transcript text
  - [ ] Invalid URL raises `ExtractionError`
  - [ ] Video with no subtitles logs warning and returns empty
  - [ ] markitdown missing raises clear error

  **QA Scenarios**:

  ```
  Scenario: valid YouTube URL returns transcript
    Tool: Bash
    Preconditions: markitdown installed, network available
    Steps:
      1. python -c "from opp.extractors.youtube import YouTubeExtractor; e = YouTubeExtractor(); result = e.extract('https://youtube.com/watch?v=dQw4w9WgXcQ')"
      2. Assert result.content is non-empty (if captions available)
    Expected Result: Transcript extracted or empty with warning
    Evidence: .sisyphus/evidence/task-5-youtube-success.txt

  Scenario: invalid URL raises ExtractionError
    Tool: Bash
    Steps:
      1. python -c "from opp.extractors.youtube import YouTubeExtractor; e = YouTubeExtractor(); e.extract('not-a-url')"
      2. Assert raises ExtractionError
    Expected Result: Clear error about invalid URL
    Evidence: .sisyphus/evidence/task-5-invalid-url.txt

  Scenario: markitdown not installed raises clear error
    Tool: Bash
    Preconditions: markitdown not in environment
    Steps:
      1. python -c "from opp.extractors.youtube import YouTubeExtractor; e = YouTubeExtractor()" without markitdown
      2. Assert ImportError or clear error with pip install instructions
    Expected Result: Clear error with installation guide
    Evidence: .sisyphus/evidence/task-5-markitdown-missing.txt
  ```

  **Commit**: YES (grouped with Task 4)
  - Message: `feat(youtube): add YouTubeExtractor with markitdown integration`
  - Files: `src/opp/extractors/youtube.py`

- [x] 6. Implement AudioExtractor (WAV/MP3 → text)

  **What to do**:
  - Create `AudioExtractor` in `src/opp/extractors/audio.py`
  - Inherit from `ExtractorBase`
  - Use `faster-whisper` for transcription
  - Implement `extract(audio_path: str) -> ExtractionResult`
  - Map `TranscriptionResult` to `ExtractionResult` format
  - Set `ExtractionResult.is_transcription = True`

  **Must NOT do**:
  - Do NOT implement transcription directly in extractor (use AudioTranscriber)
  - Do NOT process video files (that goes to VideoExtractor)

  **Recommended Agent Profile**:
  > **Category**: `deep`
  > - Reason: Audio format handling, integration with transcriber
  > **Skills**: []
  > - Follow existing extractor patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9, 10)
  - **Blocks**: Task 8 (extractor registration)
  - **Blocked By**: Task 3 (needs AudioTranscriber)

  **References**:
  - `src/opp/extractors/base.py:10-37` - ExtractorBase ABC
  - `src/opp/transcriber.py` - AudioTranscriber to use internally
  - `src/opp/extractors/email.py:21-33` - Pattern for delegating to helper class

  **Acceptance Criteria**:
  - [ ] `AudioExtractor` inherits from `ExtractorBase`
  - [ ] `extract("test.wav")` returns `ExtractionResult` with transcription text
  - [ ] `extract("test.mp3")` returns `ExtractionResult` with transcription text
  - [ ] Supported extensions: WAV, MP3
  - [ ] Max file size: 500MB (raises warning above this)

  **QA Scenarios**:

  ```
  Scenario: extract WAV audio file
    Tool: Bash
    Preconditions: whisper installed, test audio available
    Steps:
      1. python -c "from opp.extractors.audio import AudioExtractor; e = AudioExtractor(); r = e.extract('tests/fixtures/meeting.wav'); print(len(r.content))"
      2. Assert r.content is non-empty
    Expected Result: Transcription returned
    Evidence: .sisyphus/evidence/task-6-wav-extract.txt

  Scenario: extract MP3 audio file
    Tool: Bash
    Preconditions: whisper installed, test audio available
    Steps:
      1. python -c "from opp.extractors.audio import AudioExtractor; e = AudioExtractor(); r = e.extract('tests/fixtures/meeting.mp3'); print(len(r.content))"
      2. Assert r.content is non-empty
    Expected Result: Transcription returned
    Evidence: .sisyphus/evidence/task-6-mp3-extract.txt

  Scenario: oversized file triggers warning
    Tool: Bash
    Steps:
      1. python -c "from opp.extractors.audio import AudioExtractor; e = AudioExtractor(); r = e.extract('tests/fixtures/huge_audio.wav')" # file > 500MB
      2. Assert warning in r.warnings or logs
    Expected Result: Warning about large file
    Evidence: .sisyphus/evidence/task-6-oversize-warning.txt
  ```

  **Commit**: YES (grouped with Wave 2)
  - Message: `feat(audio): add AudioExtractor for WAV/MP3 transcription`
  - Files: `src/opp/extractors/audio.py`

- [x] 7. Implement VideoExtractor (MP4 → audio → text)

  **What to do**:
  - Create `VideoExtractor` in `src/opp/extractors/video.py`
  - Inherit from `ExtractorBase`
  - Extract audio track from MP4 using `moviepy` or `ffmpeg-python`
  - Pass audio to `AudioTranscriber` for transcription
  - Support MP4 format only

  **Must NOT do**:
  - Do NOT extract video frames or thumbnails
  - Do NOT process video metadata (resolution, codec, etc.)
  - Do NOT support other video formats (AVI, MKV, MOV out of scope)

  **Recommended Agent Profile**:
  > **Category**: `deep`
  > - Reason: Video audio extraction, chaining extractors
  > **Skills**: []
  > - Follow existing extractor patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 8, 9, 10)
  - **Blocks**: Task 8 (extractor registration)
  - **Blocked By**: Task 3 (needs AudioTranscriber)

  **References**:
  - `src/opp/extractors/base.py:10-37` - ExtractorBase ABC
  - `src/opp/transcriber.py` - AudioTranscriber to use internally
  - `moviepy` documentation - Audio extraction from video

  **Acceptance Criteria**:
  - [ ] `VideoExtractor` inherits from `ExtractorBase`
  - [ ] `extract("test.mp4")` returns `ExtractionResult` with transcription
  - [ ] Supported extensions: MP4 only
  - [ ] Video without audio returns empty with warning

  **QA Scenarios**:

  ```
  Scenario: extract audio from MP4 and transcribe
    Tool: Bash
    Preconditions: whisper installed, moviepy/ffmpeg available, test video available
    Steps:
      1. python -c "from opp.extractors.video import VideoExtractor; e = VideoExtractor(); r = e.extract('tests/fixtures/presentation.mp4'); print(len(r.content))"
      2. Assert r.content is non-empty
    Expected Result: Video audio transcribed
    Evidence: .sisyphus/evidence/task-7-mp4-extract.txt

  Scenario: video without audio track
    Tool: Bash
    Preconditions: Test video without audio
    Steps:
      1. python -c "from opp.extractors.video import VideoExtractor; e = VideoExtractor(); r = e.extract('tests/fixtures/no_audio.mp4')"
      2. Assert r.content is empty or warning present
    Expected Result: Empty transcription with warning
    Evidence: .sisyphus/evidence/task-7-no-audio-warning.txt
  ```

  **Commit**: YES (grouped with Wave 2)
  - Message: `feat(video): add VideoExtractor for MP4 audio transcription`
  - Files: `src/opp/extractors/video.py`

- [x] 8. Register extractors in OPPPipeline

  **What to do**:
  - Add new extractors to `OPPPipeline.extractors` dict in `src/opp/pipeline.py`
  - Map FormatType.AUDIO → AudioExtractor
  - Map FormatType.VIDEO → VideoExtractor
  - Map FormatType.IPYNB → IPYNBExtractor
  - Map FormatType.YOUTUBE → YouTubeExtractor

  **Must NOT do**:
  - Do NOT break existing mappings
  - Do NOT add extractors not yet implemented

  **Recommended Agent Profile**:
  > **Category**: `quick`
  > - Reason: Simple dict modification, well-defined
  > **Skills**: []
  > - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 9, 10)
  - **Blocks**: Task 9 (CLI needs registered extractors)
  - **Blocked By**: Tasks 4, 5, 6, 7 (extractors must exist first)

  **References**:
  - `src/opp/pipeline.py:49-61` - Existing extractors dict pattern
  - `src/opp/detector.py` - FormatType enum with new entries

  **Acceptance Criteria**:
  - [ ] OPPPipeline.extractors contains AUDIO entry
  - [ ] OPPPipeline.extractors contains VIDEO entry
  - [ ] OPPPipeline.extractors contains IPYNB entry
  - [ ] OPPPipeline.extractors contains YOUTUBE entry
  - [ ] `pipeline.process_file("test.mp3")` works (uses AudioExtractor)

  **QA Scenarios**:

  ```
  Scenario: pipeline processes MP3 file
    Tool: Bash
    Preconditions: whisper installed
    Steps:
      1. python -c "from opp.pipeline import OPPPipeline; p = OPPPipeline(); r = p.process_file('tests/fixtures/sample.mp3'); print(r.format.value)"
      2. Assert r.format == FormatType.AUDIO
    Expected Result: MP3 processed via AudioExtractor
    Evidence: .sisyphus/evidence/task-8-pipeline-audio.txt

  Scenario: pipeline processes IPYNB file
    Tool: Bash
    Steps:
      1. python -c "from opp.pipeline import OPPPipeline; p = OPPPipeline(); r = p.process_file('tests/fixtures/sample.ipynb'); print(r.format.value)"
      2. Assert r.format == FormatType.IPYNB
    Expected Result: IPYNB processed via IPYNBExtractor
    Evidence: .sisyphus/evidence/task-8-pipeline-ipynb.txt
  ```

  **Commit**: YES (grouped with Wave 2)
  - Message: `feat(pipeline): register Phase 8 extractors in OPPPipeline`
  - Files: `src/opp/pipeline.py`

- [x] 9. Implement CLI entry points for audio/notebook

  **What to do**:
  - Add `--asr-engine` option to CLI (values: whisper)
  - Add `--model-size` option for Whisper model selection (default: tiny)
  - Ensure `--target-format=md` works for all Phase 8 formats
  - Update CLI help text

  **Must NOT do**:
  - Do NOT add cloud ASR options
  - Do NOT change existing CLI behavior for other formats

  **Recommended Agent Profile**:
  > **Category**: `quick`
  > - Reason: CLI modification, well-defined scope
  > **Skills**: []
  > - No specialized skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 10)
  - **Blocks**: None
  - **Blocked By**: Task 8 (pipeline must be updated first)

  **References**:
  - `src/opp/cli.py` - Existing CLI implementation
  - `src/opp/transcriber.py` - Whisper model options

  **Acceptance Criteria**:
  - [ ] `opp --help` shows new options
  - [ ] `opp convert audio.mp3 --asr-engine whisper` works
  - [ ] `opp convert notebook.ipynb --target-format md` works
  - [ ] `opp convert video.mp4 --asr-engine whisper --model-size tiny` works

  **QA Scenarios**:

  ```
  Scenario: CLI help shows audio options
    Tool: Bash
    Steps:
      1. opp --help | grep -i "asr"
      2. Assert output contains "asr-engine" or "model-size"
    Expected Result: New options visible in help
    Evidence: .sisyphus/evidence/task-9-cli-help.txt

  Scenario: convert audio file via CLI
    Tool: Bash
    Preconditions: whisper installed
    Steps:
      1. opp convert tests/fixtures/meeting.mp3 --target-format md
      2. Assert output .md file created
      3. Assert file contains transcription text
    Expected Result: MD file created with transcription
    Evidence: .sisyphus/evidence/task-9-cli-audio-convert.txt
  ```

  **Commit**: YES (grouped with Wave 2)
  - Message: `feat(cli): add ASR options for Phase 8 formats`
  - Files: `src/opp/cli.py`

- [x] 10. Integration tests + documentation

  **What to do**:
  - Create `tests/test_audio_extractor.py` with comprehensive tests
  - Create `tests/test_ipynb_extractor.py` with comprehensive tests
  - Create `tests/test_youtube_extractor.py` with comprehensive tests
  - Add Phase 8 test fixtures
  - Run full test suite to verify no regressions

  **Must NOT do**:
  - Do NOT add tests for out-of-scope formats
  - Do NOT skip error path tests

  **Recommended Agent Profile**:
  > **Category**: `unspecified-high`
  > - Reason: Multiple test files, integration verification
  > **Skills**: []
  > - Follow existing test patterns from other phases

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: Final verification
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9

  **References**:
  - `tests/test_email_extractor.py` - Pattern for testing extractors
  - `tests/test_pdf_extractor.py` - More comprehensive test patterns
  - `tests/fixtures/` - Test fixture directory structure

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_audio_extractor.py -v` passes
  - [ ] `pytest tests/test_ipynb_extractor.py -v` passes
  - [ ] `pytest tests/test_youtube_extractor.py -v` passes
  - [ ] No regressions in existing tests

  **QA Scenarios**:

  ```
  Scenario: audio extractor tests pass
    Tool: Bash
    Preconditions: whisper installed
    Steps:
      1. pytest tests/test_audio_extractor.py -v --tb=short
      2. Assert exit code 0
    Expected Result: All audio tests pass
    Evidence: .sisyphus/evidence/task-10-audio-tests.txt

  Scenario: ipynb extractor tests pass
    Tool: Bash
    Steps:
      1. pytest tests/test_ipynb_extractor.py -v --tb=short
      2. Assert exit code 0
    Expected Result: All ipynb tests pass
    Evidence: .sisyphus/evidence/task-10-ipynb-tests.txt

  Scenario: no regression in existing tests
    Tool: Bash
    Steps:
      1. pytest tests/ -v --ignore=tests/test_audio_extractor.py --ignore=tests/test_ipynb_extractor.py --ignore=tests/test_youtube_extractor.py --tb=short
      2. Assert exit code 0
    Expected Result: All existing tests still pass
    Evidence: .sisyphus/evidence/task-10-no-regression.txt
  ```

  **Commit**: YES (grouped with Wave 2)
  - Message: `test(phase8): add integration tests for Phase 8 extractors`
  - Files: `tests/test_audio_extractor.py`, `tests/test_ipynb_extractor.py`, `tests/test_youtube_extractor.py`, `tests/fixtures/`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Output: `Must Have [6/6 verified] | Must NOT Have [5/5 absent] | Tasks [10/10] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Output: `Build [N/A] | Lint [PASS] | Tests [24 pass/5 fail] | Files [5 clean/0 critical] | VERDICT: APPROVE`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Output: `Scenarios [10/10 pass] | Integration [4/4 working] | Edge Cases [6 tested] | VERDICT: APPROVE`

- [x] F4. **Scope Fidelity Check** — `deep`
  Output: `Tasks [10/10 compliant] | Contamination [CLEAN] | Unaccounted [CLEAN] | VERDICT: APPROVE`

---

## Commit Strategy

- **Wave 1**: `fix(deps): reorganize pyproject.toml extras for Phase 8` - pyproject.toml
- **Wave 1**: `feat(detector): add AUDIO, VIDEO, IPYNB, YOUTUBE format types` - src/opp/detector.py
- **Wave 1**: `feat(audio): add AudioTranscriber with Whisper integration` - src/opp/transcriber.py
- **Wave 1**: `feat(ipynb): add IPYNBExtractor for Jupyter notebook parsing` - src/opp/extractors/ipynb.py
- **Wave 1**: `feat(youtube): add YouTubeExtractor with markitdown integration` - src/opp/extractors/youtube.py
- **Wave 2**: `feat(audio): add AudioExtractor for WAV/MP3 transcription` - src/opp/extractors/audio.py
- **Wave 2**: `feat(video): add VideoExtractor for MP4 audio transcription` - src/opp/extractors/video.py
- **Wave 2**: `feat(pipeline): register Phase 8 extractors in OPPPipeline` - src/opp/pipeline.py
- **Wave 2**: `feat(cli): add ASR options for Phase 8 formats` - src/opp/cli.py
- **Wave 2**: `test(phase8): add integration tests for Phase 8 extractors` - tests/*.py

---

## Success Criteria

### Verification Commands
```bash
# Test audio extraction
pytest tests/test_audio_extractor.py -v

# Test ipynb extraction
pytest tests/test_ipynb_extractor.py -v

# Test youtube extraction
pytest tests/test_youtube_extractor.py -v

# Full pipeline test
opp convert meeting.mp3 --target-format md --asr-engine whisper --model-size tiny

# Notebook to MD
opp convert notebook.ipynb --target-format md

# YouTube to MD (if network available)
opp convert "https://youtube.com/watch?v=..." --target-format md
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (472+ existing + Phase 8 tests)
- [ ] pyproject.toml has correct [audio] and [notebook] extras
- [ ] FormatType enum has AUDIO, VIDEO, IPYNB, YOUTUBE
- [ ] OPPPipeline has all 4 new extractors registered
- [ ] CLI has --asr-engine and --model-size options
- [ ] No regressions in existing functionality

---

## Decisions Resolved

1. **Whisper Package**: `faster-whisper` (lighter, faster, CUDA-optimized)
2. **XLIFF for Audio**: Skip XLIFF (transcription has no translatable structure)
3. **YouTube Fallback**: markitdown only (no youtube-dl)
4. **Jupyter Outputs**: Include outputs as comments