"""Small FastAPI surface for the fictional-policy RAG companion."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from examples.insurance_rag.retriever import PolicyKnowledgeAssistant


POLICY_PATH = Path(__file__).with_name("fictional_policy.json")


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000)


class CitationResponse(BaseModel):
    document_id: str
    citation: str
    score: float


class AskResponse(BaseModel):
    status: str
    answer: str
    citations: list[CitationResponse]
    retrieval_method: str
    human_review_required: bool
    disclaimer: str


def create_app(assistant: PolicyKnowledgeAssistant | None = None) -> FastAPI:
    active = assistant or PolicyKnowledgeAssistant(POLICY_PATH)
    app = FastAPI(
        title="Fictional Insurance Policy RAG",
        version="0.1.0",
        description="Portfolio-only citation retrieval over a fictional policy.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "semantic_ready": active.semantic_ready,
            "documents": len(active.documents),
            "fictional_data_only": True,
        }

    @app.post("/ask", response_model=AskResponse)
    def ask(request: AskRequest) -> dict[str, object]:
        return active.ask(request.question)

    return app


app = create_app()
