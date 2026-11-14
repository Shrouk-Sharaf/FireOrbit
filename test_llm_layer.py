"""Tests for the LLM layer. Gemini is mocked, so no API key or network is needed.

Run from the repository root:  python -m pytest test_llm_layer.py
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from llm import generate_answer  # noqa: E402
from llm.llm_client import DEFAULT_MODEL, GeminiClient, LLMConfig, LLMError  # noqa: E402
from llm.prompt import SYSTEM_PROMPT, normalize_chunk  # noqa: E402


class FakeClient:
    model = "gemini-3.8-flash"

    def __init__(self, reply="ok"):
        self.reply, self.calls = reply, []

    def generate(self, prompt, system_instruction):
        self.calls.append((prompt, system_instruction))
        return self.reply


# Shaped exactly like Retriever.search() output (chunk_id / text / metadata / *_score).
REPORT_HIT = {
    "chunk_id": "101 SAME-R/SAMER_Final 0602 2014.pdf::page-12::chunk-0003",
    "text": "Smoke particle size was measured at several inlet velocities.",
    "metadata": {"source_file": "extracted_pdf_reports.json", "document_type": "report",
                 "filename": "SAMER_Final 0602 2014.pdf", "psi_id": "PSI-101", "page": 12},
    "dense_score": 0.71, "bm25_score": 9.2, "rrf_score": 0.032,
}
RECORD_HIT = {
    "chunk_id": "experiment-PSI-98-S1-R1::chunk-0001",
    "text": "Experiment Id: PSI-98-S1-R1\nO2 Concentration Pct: 21.6\nBurn Time S: 420.0",
    "metadata": {"source_file": "experiments_normalized.json", "document_type": "experiment_record",
                 "experiment_id": "PSI-98-S1-R1", "psi_id": "PSI-98", "acronym": "SAFFIRE-I"},
    "rrf_score": 0.03,
}
INVEST_HIT = {
    "chunk_id": "investigation-PSI-100::chunk-0001",
    "text": "Title: Spacecraft Fire Experiment-III\nObjective: determine how rapidly a large fire grows.",
    "metadata": {"source_file": "investigations_metadata.json", "document_type": "investigation_metadata",
                 "psi_id": "PSI-100", "acronym": "SAFFIRE-III", "title": "Spacecraft Fire Experiment-III"},
}
HITS = [REPORT_HIT, RECORD_HIT, INVEST_HIT]


def test_response_shape_and_source_labels():
    fake = FakeClient("Smoke size was measured [1]. SAFFIRE-I burned 420 s [2][2].")
    out = generate_answer("q", HITS, client=fake)
    assert set(out) == {"answer", "sources", "model"}
    assert out["model"] == "gemini-3.8-flash"
    assert len(out["sources"]) == 2
    report, record = out["sources"]
    assert (report["source"], report["page"], report["psi_id"]) == ("SAMER_Final 0602 2014.pdf", 12, "PSI-101")
    assert record["source"] == "Experiment record PSI-98-S1-R1 (SAFFIRE-I)" and record["page"] is None


def test_investigation_label():
    n = normalize_chunk(INVEST_HIT)
    assert n["source"] == "Investigation metadata PSI-100 - Spacecraft Fire Experiment-III"
    assert n["document_type"] == "investigation_metadata"


def test_json_filename_never_used_as_source_for_records():
    assert "experiments_normalized" not in normalize_chunk(RECORD_HIT)["source"]


def test_hallucinated_citation_number_is_ignored():
    out = generate_answer("q", HITS, client=FakeClient("Claim [99] and [3]."))
    assert [s["psi_id"] for s in out["sources"]] == ["PSI-100"]


def test_same_source_and_page_merge_ids():
    twin = {**REPORT_HIT, "chunk_id": "x"}
    out = generate_answer("q", [REPORT_HIT, twin], client=FakeClient("a [1] b [2]"))
    assert len(out["sources"]) == 1 and out["sources"][0]["ids"] == [1, 2]


def test_no_citations_gives_warning_and_no_invented_sources():
    out = generate_answer("q", HITS, client=FakeClient("An answer without markers."))
    assert out["sources"] == [] and "did not cite" in out["warning"]


def test_cited_answer_has_no_warning_key():
    assert "warning" not in generate_answer("q", HITS, client=FakeClient("x [1]"))


def test_citation_lists_and_ranges_are_understood():
    out = generate_answer("q", HITS, client=FakeClient("a [1, 3] and b [2-3]"))
    assert sorted(i for s in out["sources"] for i in s["ids"]) == [1, 2, 3]
    out = generate_answer("q", HITS, client=FakeClient("a [1-99]"))  # out-of-range part is ignored
    assert sorted(i for s in out["sources"] for i in s["ids"]) == [1, 2, 3]


def test_total_matches_note_is_sent_when_only_part_is_shown():
    fake = FakeClient("5 of 79 shown [1]")
    out = generate_answer("which tests reached 85% O2?", HITS, client=fake, total_matches=79)
    prompt, system = fake.calls[0]
    assert "3 of 79" in prompt and "Retrieval note" in prompt
    assert prompt.index("Retrieval note") < prompt.index("Question:")
    assert "Retrieval note" in system  # rule 9 explains how to use the note
    assert (out["total_matches"], out["shown"]) == (79, 3)


def test_no_total_note_when_everything_is_shown_or_not_given():
    for total in (None, 3, 2):
        fake = FakeClient("x [1]")
        out = generate_answer("q", HITS, client=fake, total_matches=total)
        assert "Retrieval note" not in fake.calls[0][0]
        assert ("total_matches" in out) == (total is not None)


def test_zero_total_with_no_chunks_does_not_call_llm():
    fake = FakeClient()
    out = generate_answer("tests at 250% oxygen", [], client=fake, total_matches=0)
    assert fake.calls == [] and out["sources"] == []


def test_empty_retrieval_skips_llm():
    fake = FakeClient()
    out = generate_answer("anything", [], client=fake)
    assert fake.calls == [] and out["sources"] == []
    assert "insufficient" in out["answer"].lower()


def test_blank_text_chunks_count_as_empty():
    fake = FakeClient()
    generate_answer("q", [{"text": "  ", "metadata": {}}], client=fake)
    assert fake.calls == []


def test_insufficient_tag_stripped_and_no_sources():
    out = generate_answer("q", HITS, client=FakeClient("[[INSUFFICIENT_CONTEXT]] No ignition data is given."))
    assert out["answer"] == "No ignition data is given." and out["sources"] == []


def test_prompt_contains_context_metadata_and_rules():
    fake = FakeClient("x [1]")
    generate_answer("What material?", HITS, client=fake)
    prompt, system = fake.calls[0]
    assert "[1] Source: SAMER_Final 0602 2014.pdf | Page: 12 | Investigation: PSI-101 | Type: report" in prompt
    assert "[2] Source: Experiment record PSI-98-S1-R1 (SAFFIRE-I) | Investigation: PSI-98" in prompt
    assert "Page:" not in prompt.split("[2]")[1].split("\n")[0]  # no page for records
    assert "Question: What material?" in prompt
    assert "ONLY" in system and "insufficient" in SYSTEM_PROMPT.lower()
    assert "dense_score" not in prompt and "rrf_score" not in prompt  # scores are not sent to the LLM


def test_normalize_chunk_other_shapes():
    assert normalize_chunk("plain")["text"] == "plain"
    n = normalize_chunk({"page_content": "t", "metadata": {"filename": "a.pdf", "page_num": 3}})
    assert (n["source"], n["page"]) == ("a.pdf", 3)


def test_empty_question_rejected():
    with pytest.raises(ValueError):
        generate_answer("  ", HITS, client=FakeClient())


def test_config_defaults_and_env_override(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert LLMConfig.from_env().model == DEFAULT_MODEL == "gemini-3.5-flash-lite"
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    assert LLMConfig.from_env().model == "custom-model"


def test_missing_api_key_raises(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(LLMError, match="API key"):
        GeminiClient(LLMConfig(api_key=None)).generate("p", "s")


def test_verify_model_failure_is_loud_not_silent_fallback():
    client = GeminiClient(LLMConfig(api_key="k", model="gemini-3.8-flash"))

    class Sdk:
        class models:
            @staticmethod
            def get(model):
                raise RuntimeError("404 not found")

    client._sdk = Sdk()
    with pytest.raises(LLMError, match="gemini-3.8-flash"):
        client.verify_model()


def test_client_generate_uses_configured_model_and_rejects_empty():
    pytest.importorskip("google.genai")
    seen = {}

    class Resp:
        def __init__(self, text):
            self.text = text

    class Models:
        reply = "  hello  "

        def generate_content(self, model, contents, config):
            seen["model"] = model
            return Resp(self.reply)

    class Sdk:
        models = Models()

    client = GeminiClient(LLMConfig(api_key="k", model="gemini-3.8-flash"))
    client._sdk = Sdk()
    assert client.generate("p", "s") == "hello" and seen["model"] == "gemini-3.8-flash"
    Models.reply = ""
    with pytest.raises(LLMError, match="empty"):
        client.generate("p", "s")


@pytest.mark.skipif(not (ROOT / "chunking" / "chunks.json").exists(), reason="chunks.json not present")
def test_every_real_chunk_normalizes_with_a_usable_source():
    chunks = json.load(open(ROOT / "chunking" / "chunks.json", encoding="utf-8"))
    for c in chunks:
        n = normalize_chunk(c)
        assert n["text"] and n["source"] and n["chunk_id"]
        assert "_normalized.json" not in n["source"] and not n["source"].endswith("reports.json")
        if c["metadata"]["document_type"] == "report":
            assert n["page"] is not None
