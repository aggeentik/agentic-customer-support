"""
Pydantic schemas for the CRM ↔ Supervisor API contract.

CRM sends a CRMRequest; Supervisor returns a SupervisorResponse.
Both are serialised as JSON.  All fields are required unless Optional.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RequestType(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    BUSINESS_WORKFLOW = "BUSINESS_WORKFLOW"
    UNKNOWN = "UNKNOWN"


class WorkflowStatus(str, Enum):
    INITIATED = "INITIATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    MISSING_PARAMS = "MISSING_PARAMS"


# ---------------------------------------------------------------------------
# Inbound — CRM → Supervisor
# ---------------------------------------------------------------------------


class ConversationTurn(BaseModel):
    role: str = Field(..., description="'customer' or 'agent'")
    content: str


class CRMRequest(BaseModel):
    customer_query: str = Field(..., description="Latest customer message")
    customer_id: Optional[str] = Field(None, description="CRM customer identifier")
    ticket_id: Optional[str] = Field(None, description="Active support ticket ID")
    conversation_history: List[ConversationTurn] = Field(
        default_factory=list,
        description="Prior turns, oldest first",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Any CRM-specific context (order IDs, transaction IDs, etc.)",
    )


# ---------------------------------------------------------------------------
# Outbound — Supervisor → CRM
# ---------------------------------------------------------------------------


class Source(BaseModel):
    uri: str = Field(..., description="Document URI from Knowledge Base")
    text: str = Field(..., description="Chunk text that was cited")
    score: float = Field(..., ge=0.0, le=1.0, description="Retrieval relevance score")


class WorkflowAction(BaseModel):
    action: str = Field(..., description="Name of the workflow tool that was called")
    status: WorkflowStatus
    workflow_id: Optional[str] = Field(None, description="Step Functions execution ARN")
    message: Optional[str] = Field(None, description="Human-readable status detail")


class SupervisorResponse(BaseModel):
    request_type: RequestType
    classification: str = Field(..., description="Fine-grained label, e.g. 'refund_request'")
    response: str = Field(..., description="Suggested reply for the human agent to review")
    sources: List[Source] = Field(
        default_factory=list,
        description="Citations — populated for INFORMATIONAL responses",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    escalation_needed: bool = Field(
        False,
        description="True when confidence < 0.7 or request is outside agent scope",
    )
    workflow_actions: List[WorkflowAction] = Field(
        default_factory=list,
        description="Actions taken — populated for BUSINESS_WORKFLOW responses",
    )
