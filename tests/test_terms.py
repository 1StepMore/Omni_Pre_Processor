"""OPP#116 M3: mechanical term-candidate extraction — structure + artifact locks."""

import json
from pathlib import Path

from opp.terms import extract_term_candidates, write_terms_json
from opp.utils.dataclasses import ParagraphData


def _paragraphs(*texts: str) -> list[ParagraphData]:
    return [ParagraphData(text=t, position=i) for i, t in enumerate(texts)]


class TestTermCandidateExtraction:
    """Structure lock: what counts as a candidate and what is recorded."""

    def test_acronym_candidate(self):
        candidates = extract_term_candidates(_paragraphs("The API and the API again."))
        api = next(c for c in candidates if c.term == "API")
        assert api.frequency == 2
        assert api.first_paragraph == 0
        assert api.first_char_offset == 4  # "The " = 4 chars
        assert api.variants == ["API"]

    def test_camel_case_candidate(self):
        candidates = extract_term_candidates(_paragraphs("GitHub hosts JavaScript code."))
        terms = {c.term for c in candidates}
        assert "GitHub" in terms
        assert "JavaScript" in terms

    def test_proper_noun_sequence(self):
        candidates = extract_term_candidates(_paragraphs("The United Nations met."))
        terms = {c.term for c in candidates}
        assert "United Nations" in terms

    def test_case_variants_merge_with_first_seen_canonical(self):
        candidates = extract_term_candidates(
            _paragraphs("Use GitHub daily.", "GITHUB is the same word.", "GitHUB too.")
        )
        gh = next(c for c in candidates if c.term.casefold() == "github")
        assert gh.term == "GitHub"              # first-seen form is canonical
        assert gh.frequency == 3
        assert gh.variants == ["GitHub", "GITHUB", "GitHUB"]
        assert (gh.first_paragraph, gh.first_char_offset) == (0, 4)

    def test_first_occurrence_coordinates_are_document_order(self):
        candidates = extract_term_candidates(
            _paragraphs("Nothing here.", "Second paragraph mentions JSON once.")
        )
        js = next(c for c in candidates if c.term == "JSON")
        assert (js.first_paragraph, js.first_char_offset) == (1, 26)

    def test_sorting_frequency_desc_then_position(self):
        candidates = extract_term_candidates(
            _paragraphs(
                "ZZ appears once.",            # ZZ: freq 1, para 0
                "AA and BB.",                  # AA, BB: freq 1, para 1
                "AA again and BB again.",      # AA, BB -> freq 2
            )
        )
        by_term = {c.term: c for c in candidates}
        assert by_term["AA"].frequency == 2
        assert by_term["BB"].frequency == 2
        assert by_term["ZZ"].frequency == 1
        # frequency desc; ties broken by (first_paragraph, first_char_offset)
        ordered = [c.term for c in candidates]
        assert ordered.index("AA") < ordered.index("BB") < ordered.index("ZZ")

    def test_lowercase_words_never_match(self):
        candidates = extract_term_candidates(_paragraphs("plain lowercase words only"))
        assert candidates == []

    def test_empty_paragraph_list(self):
        assert extract_term_candidates([]) == []


class TestTermsJsonArtifact:
    """Structure lock: the terms.json envelope written next to other artifacts."""

    def test_writes_schema_with_count(self, tmp_path):
        paragraphs = _paragraphs("The API and the NASA rocket.", "NASA again.")
        out = tmp_path / "doc_terms.json"

        result = write_terms_json(paragraphs, out)

        assert result is not None and len(result) >= 2
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["count"] == len(payload["terms"])
        assert payload["count"] >= 2
        for entry in payload["terms"]:
            assert set(entry) == {
                "term",
                "frequency",
                "first_paragraph",
                "first_char_offset",
                "variants",
            }
            assert isinstance(entry["variants"], list) and entry["variants"]
        nasa = next(e for e in payload["terms"] if e["term"] == "NASA")
        assert nasa["frequency"] == 2

    def test_no_candidates_writes_nothing(self, tmp_path):
        out = tmp_path / "doc_terms.json"
        result = write_terms_json(_paragraphs("plain lowercase text only"), out)
        assert result is None
        assert not out.exists()


class TestTermsJsonFromExtract:
    """Acceptance anchor: a real extract_document run emits terms.json."""

    def _run_extract(self, tmp_path: Path) -> Path:
        import argparse

        from opp.cli import process_single_file
        from opp.error_handler import ErrorHandler
        from opp.pipeline import OPPPipeline

        source = tmp_path / "termsdoc.json"
        source.write_text(
            json.dumps({"title": "API Guide", "body": "GitHub serves the NASA dataset. NASA again."}),
            encoding="utf-8",
        )
        output_dir = tmp_path / "out"
        args = argparse.Namespace(
            target_format="md",
            output_dir=output_dir,
            style_map=None,
            no_embed_images=False,
            source_lang="en",
            target_lang="zh",
            ocr_engine=None,
            ocr_lang=None,
            asr_engine=None,
            model_size=None,
            log_format=None,
            resource_dir=tmp_path / "resources",
        )
        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        stats: dict = {"files_processed": 0, "errors": 0}
        ok = process_single_file(source, args, pipeline, stats, ErrorHandler())
        assert ok, "extraction must succeed"
        return output_dir

    def test_extract_document_emits_terms_json(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPP_TERMS_JSON", raising=False)
        output_dir = self._run_extract(tmp_path)
        terms_path = output_dir / "termsdoc_terms.json"
        assert terms_path.exists(), "extract_document must emit terms.json (OPP#116 M3)"
        payload = json.loads(terms_path.read_text(encoding="utf-8"))
        terms = {e["term"] for e in payload["terms"]}
        assert "NASA" in terms
        nasa = next(e for e in payload["terms"] if e["term"] == "NASA")
        # The JSON extractor emits the document twice (fenced dump +
        # json_field lines), so "NASA … NASA" counts 2 x 2 = 4. Locks the
        # mechanism: frequency counts every occurrence in the paragraph
        # stream, whatever representation the source extractor chose.
        assert nasa["frequency"] == 4

    def test_opp_terms_json_zero_disables_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPP_TERMS_JSON", "0")
        output_dir = self._run_extract(tmp_path)
        assert not (output_dir / "termsdoc_terms.json").exists()
