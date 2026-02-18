"""
Supervisor Agent — AgentCore Runtime entrypoint.

Model  : Claude Sonnet 4.5
Role   : Central orchestrator.  Calls Classifier → routes to Informational
         or Workflow → formats the structured JSON response for the CRM.
Tools  : classifier_agent, informational_agent, workflow_agent  (agents-as-tools)
Hooks  : GuardrailHook (Bedrock Guardrails, optional)
         Observability via OTEL — Strands emits traces automatically to CloudWatch

Deploy:
    agentcore configure --entrypoint agents/supervisor_agent.py --non-interactive
    agentcore launch

Test locally:
    agentcore launch --local
    agentcore invoke '{"customer_query": "How does adaptive cruise control work on my 5 Series?"}'
    agentcore invoke '{"customer_query": "I want to book a service appointment for an oil change", "metadata": {"vehicle_vin": "WBA12345678901234", "model": "BMW 5 Series", "year": "2022"}}'
"""

from __future__ import annotations

import json
import os

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

from classifier_agent import classifier_agent
from hooks.guardrail_hook import GuardrailHook
from informational_agent import informational_agent
from workflow_agent import workflow_agent

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SUPERVISOR_PROMPT = """\
You are a supervisor agent for an automotive manufacturer's customer support team.
You coordinate specialist agents and return a structured JSON response that the
human support agent will review before contacting the customer.

For EVERY request, follow these steps exactly:

1. Call classifier_agent to determine intent (INFORMATIONAL or BUSINESS_WORKFLOW).
2. If INFORMATIONAL  → call informational_agent to retrieve a cited answer from the
                        vehicle knowledge base.
   If BUSINESS_WORKFLOW → call workflow_agent to schedule the appointment or initiate
                          the requested service process.
3. Combine the results into a single JSON response with ALL of the following fields:

{
  "request_type":      "INFORMATIONAL" | "BUSINESS_WORKFLOW",
  "classification":    "<fine-grained label, e.g. dashboard_warning_query | service_appointment_request | test_drive_booking | showroom_consultation>",
  "response":          "<suggested reply the human agent can send or adapt>",
  "sources":           [{"uri": "...", "text": "...", "score": 0.0}],
  "confidence":        0.0,
  "escalation_needed": false,
  "workflow_actions":  [{"action": "...", "status": "...", "workflow_id": "...", "message": "..."}]
}

Rules:
- Always populate all seven fields, even if sources or workflow_actions are empty lists.
- Set escalation_needed to true when: confidence < 0.7, the query is about a safety-
  critical issue (active red warning light, airbag, brake failure), the request is
  outside the agent's scope, or the workflow agent returns MISSING_PARAMS or FAILED.
- sources is empty for BUSINESS_WORKFLOW responses.
- workflow_actions is empty for INFORMATIONAL responses.
- For safety-critical informational queries, always recommend the customer contact
  their nearest authorised dealer immediately regardless of confidence.
- Maintain a professional, empathetic, and brand-appropriate tone.
- Output ONLY valid JSON — no markdown fences, no preamble.
"""

# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------

app = BedrockAgentCoreApp()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_context(payload: dict) -> str:
    """Flatten CRM payload fields into a context string for sub-agents."""
    parts: list[str] = []
    if customer_id := payload.get("customer_id"):
        parts.append(f"Customer ID: {customer_id}")
    if ticket_id := payload.get("ticket_id"):
        parts.append(f"Ticket ID: {ticket_id}")

    # Surface key vehicle fields from metadata so sub-agents can use them
    # without having to parse the full metadata dict themselves.
    metadata = payload.get("metadata", {})
    vehicle_parts: list[str] = []
    for field, label in [
        ("vehicle_vin",        "VIN"),
        ("model",              "Model"),
        ("year",               "Year"),
        ("dealership_id",      "Preferred Dealership"),
        ("mileage",            "Mileage"),
    ]:
        if value := metadata.get(field):
            vehicle_parts.append(f"{label}: {value}")
    if vehicle_parts:
        parts.append("Vehicle: " + " | ".join(vehicle_parts))

    # Pass through any remaining metadata fields as-is
    remaining = {k: v for k, v in metadata.items()
                 if k not in {"vehicle_vin", "model", "year", "dealership_id", "mileage"}}
    if remaining:
        parts.append(f"Additional metadata: {json.dumps(remaining)}")

    if history := payload.get("conversation_history"):
        formatted = "\n".join(
            f"  [{t.get('role', '?')}]: {t.get('content', '')}"
            for t in history
        )
        parts.append(f"Conversation history:\n{formatted}")
    return "\n".join(parts) if parts else "No additional context provided."


def _parse_response(raw: str) -> dict:
    """
    Extract the JSON object from the Supervisor's response.

    Falls back to a safe escalation response if parsing fails — this should
    never happen in practice but guards against model output variability.
    """
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    return {
        "request_type": "UNKNOWN",
        "classification": "parse_error",
        "response": (
            "I was unable to process your request at this time. "
            "A human agent will assist you shortly."
        ),
        "sources": [],
        "confidence": 0.0,
        "escalation_needed": True,
        "workflow_actions": [],
    }


def _build_hooks() -> list:
    if os.environ.get("BEDROCK_GUARDRAIL_ID"):
        return [GuardrailHook()]
    return []


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """
    Main handler called by AgentCore Runtime.

    Args:
        payload: Dict from the CRM POST body.  Expected keys:
                   customer_query (str, required)
                   customer_id    (str, optional)
                   ticket_id      (str, optional)
                   conversation_history (list[{role, content}], optional)
                   metadata       (dict, optional)
        context: AgentCore runtime context (provides session_id, etc.)

    Returns:
        SupervisorResponse dict — serialised to JSON by AgentCore.
    """
    customer_query = payload.get("customer_query", "")
    customer_id = payload.get("customer_id", "")
    session_id = getattr(context, "session_id", "unknown")

    context_str = _build_context(payload)

    supervisor = Agent(
        model=SONNET,
        system_prompt=SUPERVISOR_PROMPT,
        tools=[classifier_agent, informational_agent, workflow_agent],
        hooks=_build_hooks(),
        callback_handler=None,  # suppress intermediate stdout; CRM only sees the final JSON
    )

    raw_result = supervisor(
        f"Context:\n{context_str}\n\nCustomer query:\n{customer_query}",
        # invocation_state — flows into hooks via event.invocation_state
        customer_id=customer_id,
        session_id=session_id,
    )

    return _parse_response(str(raw_result))


# ---------------------------------------------------------------------------
# Local entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
