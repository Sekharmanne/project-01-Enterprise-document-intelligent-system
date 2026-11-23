import json
from threading import Barrier

import fitz
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from groq import APIStatusError
from langchain_core.runnables import RunnableLambda

from app.api.routes import router
from app.config.config import Settings
from app.services.document_workflows import PortalService


@pytest.fixture
def document_api(tmp_path):
    settings = Settings(auth_mode="local", storage_dir=tmp_path)
    app = FastAPI()
    app.state.settings = settings
    app.state.portal = PortalService(settings)
    app.include_router(router)
    with TestClient(app) as client:
        yield client, app.state.portal.document_analysis


def pdf_upload(name, pages):
    with fitz.open() as document:
        for text in pages:
            document.new_page().insert_text((50, 50), text)
        return name, document.tobytes(), "application/pdf"


def test_compare_aligns_shifted_pdf_pages_and_reports_additions_and_removals(document_api, monkeypatch):
    client, analysis = document_api
    monkeypatch.setattr(analysis, "analysis_model", lambda: RunnableLambda(lambda _: "Text changed."))

    response = client.post("/api/compare", files={
        "reference": pdf_upload("old.pdf", ["Intro", "Terms", "Old contact", "Obsolete"]),
        "actual": pdf_upload("new.pdf", ["Intro", "New material", "Terms", "New contact"]),
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["comparison_kind"] == "pages"
    # The final unmatched span pairs New contact with Old contact in document order.
    changes = result["changes"]
    assert [(item["reference_page"], item["actual_page"], item["changed"]) for item in changes] == [
        (1, 1, False), (None, 2, True), (2, 3, False), (3, 4, True), (4, None, True),
    ]
    assert changes[1]["summary"].startswith("Page added.")
    assert changes[-1]["summary"].startswith("Page removed.")


def test_long_analysis_splits_rejected_sections_and_merges_in_document_order(document_api, monkeypatch):
    client, analysis = document_api
    oversize_payloads = []
    final_payloads = []

    def respond(prompt):
        system, human = (message.content for message in prompt.to_messages())
        if system.startswith("Summarize this part"):
            if len(human) > 9_000:
                oversize_payloads.append(len(human))
                request = httpx.Request("POST", "https://example.test")
                response = httpx.Response(413, request=request)
                raise APIStatusError("Request too large", response=response, body=None)
            return human[0]
        final_payloads.append(human)
        return json.dumps({
            "title": "Test", "summary": "Combined summary", "keywords": [], "language": "en",
        })

    monkeypatch.setattr(analysis, "analysis_model", lambda: RunnableLambda(respond))
    text = "A" * 16_000 + "B" * 16_000 + "C" * 4_000
    response = client.post("/api/analyze", files={"file": ("report.txt", text, "text/plain")})

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == "Combined summary"
    assert response.json()["page_count"] == 1
    assert oversize_payloads == [16_000, 16_000]
    assert final_payloads[0].endswith("A\n\nA\n\nB\n\nB\n\nC")


def test_compare_short_text_documents_keeps_document_mode(document_api, monkeypatch):
    client, analysis = document_api
    monkeypatch.setattr(analysis, "analysis_model", lambda: RunnableLambda(lambda _: "Text changed."))
    response = client.post("/api/compare", files={
        "reference": ("old.txt", "New York", "text/plain"),
        "actual": ("new.txt", "New Delhi", "text/plain"),
    })
    assert response.status_code == 200, response.text
    assert response.json()["comparison_kind"] == "document"
    assert response.json()["changes"][0]["summary"] == "Text changed."


def test_compare_long_text_documents_combines_both_section_summaries(document_api, monkeypatch):
    client, analysis = document_api
    both_summaries_started = Barrier(2, timeout=5)

    def respond(prompt):
        system, human = (message.content for message in prompt.to_messages())
        if system.startswith("Summarize this part"):
            both_summaries_started.wait()
            return f"{human[0]} summary"
        assert human == "Reference document:\nA summary\n\nSecond document:\nB summary"
        return json.dumps({"overview": "Updated terms.", "differences": ["Terms changed."], "similarities": []})

    monkeypatch.setattr(analysis, "analysis_model", lambda: RunnableLambda(respond))
    response = client.post("/api/compare", files={
        "reference": ("old.txt", "A" * 8_000, "text/plain"),
        "actual": ("new.txt", "B" * 8_000, "text/plain"),
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["comparison_kind"] == "sections"
    assert result["overview"]["differences"] == ["Terms changed."]
    assert result["reference_sections"] == ["A summary"]
    assert result["actual_sections"] == ["B summary"]
