from __future__ import annotations

from collections.abc import Mapping

import pytest

from agent.manager_chat import ManagerChatService
from saas.store import ConversationNotFoundError, SaaSStore, SaaSStoreError


def _analysis(*, freshness: str = "rotten") -> dict[str, object]:
    return {
        "decision": "accept_prediction",
        "status": "completed",
        "prediction": {
            "class_name": f"{freshness}orange",
            "display_name": f"{freshness.title()} Orange",
            "fruit": "orange",
            "freshness": freshness,
            "confidence": 0.93,
        },
        "reasoning": {"risk_level": "high" if freshness == "rotten" else "low"},
        "warnings": [{"level": "warning", "message": "Visual assessment only."}],
        "recommendation": "Inspect the physical batch.",
        "safety_notice": "Not a food-safety test.",
    }


class _Retriever:
    def retrieve(self, query: str):
        return [
            {
                "id": "orange_visible_spoilage",
                "fruit": "orange",
                "topic": "visible_spoilage",
                "text": "Inspect for mold, leaking, collapse, and widespread soft areas.",
                "retrieval_method": "semantic",
                "retrieval_score": 0.91,
            }
        ]


class _Responder:
    model = "test-manager-model"

    def __init__(self) -> None:
        self.payloads: list[Mapping[str, object]] = []

    def generate(self, *, system_prompt: str, payload: Mapping[str, object]) -> str:
        self.payloads.append(payload)
        assert "Never claim a fruit is safe" in system_prompt
        return (
            "Batch OR-42 was flagged as Rotten Orange at 93% confidence. "
            "The proposed hold still requires Manager approval. "
            "[Inspection OR-42]"
        )


class _FailingResponder:
    def generate(self, *, system_prompt: str, payload: Mapping[str, object]) -> str:
        raise RuntimeError("provider unavailable")


def _store_with_inspection(tmp_path):
    store = SaaSStore(tmp_path / "manager-chat.db")
    store.workspace("manager-a")
    inspection = store.record_inspection(
        identity_hash="manager-a",
        location_name="Main store",
        batch_reference="OR-42",
        operator_note="Morning receiving check",
        analysis=_analysis(),
        model_version="0.6.0",
    )
    return store, inspection


def test_manager_chat_persists_multi_turn_history_and_grounded_citations(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    responder = _Responder()
    service = ManagerChatService(
        store,
        retriever=_Retriever(),
        responder=responder,
    )
    conversation = store.create_manager_conversation(identity_hash="manager-a")

    first = service.reply(
        identity_hash="manager-a",
        conversation_id=conversation["conversation_id"],
        content="Why did the Agent flag batch OR-42?",
    )
    second = service.reply(
        identity_hash="manager-a",
        conversation_id=conversation["conversation_id"],
        content="What should the reviewer check next?",
    )

    assert len(first.conversation["messages"]) == 2
    assert len(second.conversation["messages"]) == 4
    assert responder.payloads[1]["conversation_history"][0]["content"] == (
        "Why did the Agent flag batch OR-42?"
    )
    assistant = second.assistant_message
    assert assistant["metadata"]["source"] == "openai_rag"
    assert assistant["metadata"]["image_data_used"] is False
    assert assistant["metadata"]["actions_executed"] is False
    assert {citation["source_type"] for citation in assistant["citations"]} >= {
        "inspection",
        "knowledge",
    }
    assert conversation["conversation_id"] in {
        item["conversation_id"]
        for item in store.list_manager_conversations("manager-a")
    }


def test_manager_preferences_are_personal_and_validate_workspace_locations(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    updated = store.update_manager_preferences(
        identity_hash="manager-a",
        preferred_language="zh",
        response_detail="concise",
        default_location_name="Main store",
        review_focus="freshness_risk",
        custom_instructions="Show confidence when it is available.",
    )

    assert updated["preferred_language"] == "zh"
    assert updated["default_location_name"] == "Main store"
    assert store.manager_preferences("manager-b")["preferred_language"] == "auto"
    with pytest.raises(SaaSStoreError, match="not in this workspace"):
        store.update_manager_preferences(
            identity_hash="manager-a",
            default_location_name="Another workspace",
        )


def test_default_location_scopes_a_generic_manager_question(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    store.record_inspection(
        identity_hash="manager-a",
        location_name="Second store",
        batch_reference="OR-99",
        operator_note="Other branch",
        analysis=_analysis(freshness="fresh"),
        model_version="0.6.0",
    )
    store.update_manager_preferences(
        identity_hash="manager-a",
        default_location_name="Main store",
    )
    responder = _Responder()
    service = ManagerChatService(store, retriever=_Retriever(), responder=responder)
    conversation = store.create_manager_conversation(identity_hash="manager-a")

    service.reply(
        identity_hash="manager-a",
        conversation_id=conversation["conversation_id"],
        content="Summarize recent inspections.",
    )

    evidence = responder.payloads[0]["workspace_evidence"]
    assert {item["location_name"] for item in evidence["inspections"]} == {"Main store"}
    assert {item["batch_reference"] for item in evidence["inspections"]} == {"OR-42"}


def test_manager_chat_falls_back_without_losing_the_conversation(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    conversation = store.create_manager_conversation(identity_hash="manager-a")
    service = ManagerChatService(
        store,
        retriever=_Retriever(),
        responder=_FailingResponder(),
    )

    result = service.reply(
        identity_hash="manager-a",
        conversation_id=conversation["conversation_id"],
        content="Summarize batch OR-42",
    )

    assert result.assistant_message["metadata"]["source"] == "grounded_fallback"
    assert "OR-42" in result.assistant_message["content"]
    assert len(result.conversation["messages"]) == 2


def test_manager_conversations_are_workspace_scoped_and_archivable(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    conversation = store.create_manager_conversation(identity_hash="manager-a")

    with pytest.raises(ConversationNotFoundError):
        store.manager_conversation("manager-b", conversation["conversation_id"])

    archived = store.archive_manager_conversation(
        identity_hash="manager-a",
        conversation_id=conversation["conversation_id"],
    )
    assert archived["status"] == "archived"
    assert store.list_manager_conversations("manager-a") == []


def test_manager_conversations_are_private_between_members_in_one_workspace(tmp_path):
    store, _inspection = _store_with_inspection(tmp_path)
    invitation = store.create_invitation(
        identity_hash="manager-a",
        email="peer@example.test",
        role="reviewer",
    )
    store.accept_invitation(
        identity_hash="manager-peer",
        email="peer@example.test",
        display_name="Peer Reviewer",
        invitation_token=invitation["invitation_token"],
    )
    conversation = store.create_manager_conversation(identity_hash="manager-a")

    assert store.list_manager_conversations("manager-peer") == []
    with pytest.raises(ConversationNotFoundError):
        store.manager_conversation("manager-peer", conversation["conversation_id"])
