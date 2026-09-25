"""Pydantic request/response schemas for the wizard API."""
from typing import Optional
from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    initial_message: str = Field(..., description="The user's first description of their product idea")


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class SessionState(BaseModel):
    session_id: str
    messages: list[ChatMessage] = []
    concept_summary: Optional[str] = None
    companies: list[str] = []
    selected_name: Optional[str] = None
    selected_theme: Optional[str] = None
    modules: list[str] = []
    stage: str = "discovery"  # discovery -> research -> identity -> freeze -> generating -> manager


class ChatTurnRequest(BaseModel):
    session_id: str
    message: str


class ResearchMoreRequest(BaseModel):
    session_id: str
    query: str


class NameCheckRequest(BaseModel):
    session_id: str
    name: str


class SelectNameRequest(BaseModel):
    session_id: str
    name: str


class SelectThemeRequest(BaseModel):
    session_id: str
    theme: str


class FreezeRequest(BaseModel):
    session_id: str


class GenerateRequest(BaseModel):
    session_id: str


class Requirement(BaseModel):
    req_id: str
    module: str
    title: str
    body: str
    status: str = "Draft"  # Draft -> Review -> Approved -> Frozen
    revised_body: Optional[str] = None


class CommentRequest(BaseModel):
    req_id: str
    comment: str


class AcceptRequest(BaseModel):
    req_id: str
