from unittest.mock import call, patch

import pytest
from fastapi import HTTPException
from langchain_core.runnables import RunnableLambda

from app.ai_module.schemas import AskRequest
from app.config.config import Settings
from app.services.document_workflows import PortalService


@pytest.fixture
def session(tmp_path):
    portal = PortalService(Settings(storage_dir=tmp_path))
    session_id = portal.create_session("owner")["session_id"]
    return portal, session_id


def test_document_chat_retries_empty_rewrite_and_saves_sources(session):
    portal, session_id = session
    conversation_id = "a" * 32
    history = [{"role": "user", "content": "Tell me about KYC.", "conversation_id": conversation_id}]
    portal.warehouse.write_json(portal.warehouse.path(session_id) / "history.json", [
        *history,
        {"role": "assistant", "content": "Hello", "answer_kind": "general", "conversation_id": conversation_id},
        {"role": "user", "content": "Other topic", "conversation_id": "b" * 32},
    ])
    question = "What about renewals?"
    rewritten = "What are the KYC renewal rules?"
    hits = [{"document": "kyc.pdf", "page": 7, "score": 0.9, "text": "Renewal terms."}]

    with (
        patch.object(portal.document_chat, "rewrite_query", return_value=rewritten) as rewrite,
        patch.object(portal.index, "_search_chroma", side_effect=[[], hits]) as search,
        patch.object(portal.document_chat, "answer", return_value="See page 7.") as answer,
    ):
        response = portal.chat(
            session_id, "owner",
            AskRequest(question=question, conversation_id=conversation_id, top_k=2),
        )

    rewrite.assert_called_once_with(question, history)
    assert [entry.args[2:4] for entry in search.call_args_list] == [(rewritten, 2), (question, 2)]
    answer.assert_called_once_with(question, hits, history)
    assert response.answer == "See page 7."
    assert response.sources[0].page == 7
    saved = portal.session_detail(session_id, "owner")["history"][-2:]
    assert [turn["conversation_id"] for turn in saved] == [conversation_id, conversation_id]
    assert saved[-1]["sources"] == [source.model_dump() for source in response.sources]


def test_empty_results_and_small_talk_use_existing_answers(session):
    portal, session_id = session
    question = "What is the renewal period?"
    with (
        patch.object(portal.index, "search_locked", return_value=[]) as search,
        patch.object(portal.document_chat, "answer_directly", return_value="Hello!") as direct,
    ):
        result = portal.chat(session_id, "owner", AskRequest(question=question))
        greeting = portal.chat(session_id, "owner", AskRequest(question="Hello"))

    assert result.answer == "I don't know based on the uploaded documents."
    assert result.sources == []
    assert search.call_args_list == [call(session_id, "owner", question, k=4)]
    direct.assert_called_once_with("Hello")
    assert greeting.answer_kind == "general"


def test_missing_documents_error_leaves_history_empty(session):
    portal, session_id = session
    with pytest.raises(HTTPException) as error:
        portal.chat(session_id, "owner", AskRequest(question="What is the renewal period?"))
    assert error.value.status_code == 409
    assert portal.session_detail(session_id, "owner")["history"] == []


def test_combined_greeting_calls_model_without_document_search(session):
    portal, session_id = session
    questions = ["hello bro", "hi hello how are you", "Hey bro, how are you?", "Bhai, kya haal hai?"]
    received = []

    def reply(prompt):
        received.append(prompt.to_messages()[-1].content)
        return "Hi! I'm doing well."

    portal.document_chat.models._model = RunnableLambda(reply)
    with patch.object(portal.index, "search_locked", return_value=[]) as search:
        responses = [
            portal.direct_chat(AskRequest(question=questions[0])),
            *(portal.chat(session_id, "owner", AskRequest(question=question)) for question in questions),
        ]
        search.assert_not_called()
        document_question = "Hello bro, what is KYC?"
        portal.chat(session_id, "owner", AskRequest(question=document_question))
        search.assert_called_once_with(session_id, "owner", document_question, k=4)

    assert received == [questions[0], *questions]
    assert all(response.answer == "Hi! I'm doing well." for response in responses)
    assert all(response.answer_kind == "general" and response.sources == [] for response in responses)


def test_saved_greeting_loses_old_sources_without_affecting_document_answers(session):
    portal, session_id = session
    source = {"document": "report.pdf", "page": 1, "score": 0.9, "excerpt": "Policy terms"}
    document_turns = [
        {"role": "user", "content": "What are the policy terms?", "answer_kind": "document"},
        {"role": "assistant", "content": "See the report.", "answer_kind": "document", "sources": [source]},
    ]
    portal.warehouse.write_json(portal.warehouse.path(session_id) / "history.json", [
        {"role": "user", "content": "hello bro", "answer_kind": "document"},
        {"role": "assistant", "content": "Hello!", "answer_kind": "document", "sources": [source]},
        *document_turns,
    ])

    history = portal.session_detail(session_id, "owner")["history"]
    assert [turn["answer_kind"] for turn in history[:2]] == ["general", "general"]
    assert history[1]["sources"] == []
    assert history[2:] == document_turns

    followup = "What about renewals?"
    with (
        patch.object(portal.document_chat, "rewrite_query", return_value=followup) as rewrite,
        patch.object(portal.index, "search_locked", return_value=[]),
    ):
        portal.chat(session_id, "owner", AskRequest(question=followup))
    rewrite.assert_called_once_with(followup, document_turns)
