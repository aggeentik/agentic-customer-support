"""
Workflow Agent — business action executor.

Model  : Claude Haiku 4.5  (fast parameter extraction + tool calling)
Role   : Extract action parameters from the customer request, then call the
         appropriate business tool via AgentCore Gateway (MCP protocol).
Tools  : Loaded dynamically from AgentCore Gateway at invocation time.
Output : JSON string with action_taken, status, workflow_id, message.

Environment variables required:
    GATEWAY_MCP_URL        — AgentCore Gateway MCP endpoint URL
    GATEWAY_TOKEN_ENDPOINT — Cognito OAuth2 token endpoint
    GATEWAY_CLIENT_ID      — Cognito app client ID
    GATEWAY_CLIENT_SECRET  — Cognito app client secret
    GATEWAY_SCOPE          — OAuth2 scope (default: gateway/invoke)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

WORKFLOW_PROMPT = """\
You are an automotive customer support workflow specialist. You schedule appointments
and initiate service processes on behalf of customers via connected business tools.

Appointment types you can handle:
- Service appointment  — routine maintenance (oil change, tyre rotation, brake service,
                         inspection) or fault/warning-light diagnosis
- Recall appointment   — safety recall repair at an authorised dealer
- Showroom appointment — sales consultation with an advisor about purchasing a new vehicle
- Test drive           — arrange a test drive at a convenient dealership

Your responsibilities:
1. Extract the required parameters from the customer request and context.
   Key parameters by appointment type:

   Service / Recall:
     vehicle_vin, service_type, preferred_date, preferred_time, dealership_id,
     customer_contact_phone, fault_description (for diagnostic appointments)

   Showroom / Test drive:
     model_of_interest, preferred_date, preferred_time, dealership_id,
     customer_contact_phone, trade_in_vehicle (optional)

2. Call the appropriate scheduling tool with those parameters.
3. Report the outcome clearly with any confirmation numbers or next steps.

Output format — respond with ONLY valid JSON, no markdown fences:
{
  "action_taken": "<name of the tool called>",
  "status": "<INITIATED | COMPLETED | FAILED | PENDING_APPROVAL | MISSING_PARAMS>",
  "workflow_id": "<confirmation number or execution ID returned by the tool>",
  "message": "<human-readable summary including date, time, dealership, next steps>",
  "missing_params": ["<param1>", "<param2>"]   // only when status is MISSING_PARAMS
}

Rules:
- Call exactly ONE tool per request.
- If required parameters are missing, set status to MISSING_PARAMS and list only the
  missing ones — do NOT guess dates, dealerships, or VINs.
- If the tool returns an error, set status to FAILED with the error in message.
- NEVER expose internal system ARNs, credentials, or raw stack traces.
- For fault/warning-light appointments, note in message that the customer should not
  drive if a red warning light is active.
"""

# ---------------------------------------------------------------------------
# Token cache — avoids a Cognito round-trip on every request
# ---------------------------------------------------------------------------


class _TokenCache:
    """Thread-safe Bearer token cache with 5-minute expiry buffer."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = Lock()

    def get(self) -> str:
        with self._lock:
            if self._token and self._expires_at and datetime.now(timezone.utc) < self._expires_at:
                return self._token
            self._token, self._expires_at = self._fetch()
            return self._token

    @staticmethod
    def _fetch() -> tuple[str, datetime]:
        token_endpoint = os.environ["GATEWAY_TOKEN_ENDPOINT"]
        client_id = os.environ["GATEWAY_CLIENT_ID"]
        client_secret = os.environ["GATEWAY_CLIENT_SECRET"]
        scope = os.environ.get("GATEWAY_SCOPE", "gateway/invoke")

        resp = httpx.post(
            token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        expires_in = data.get("expires_in", 3600) - 300  # 5-min buffer
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return data["access_token"], expires_at


_token_cache = _TokenCache()

# ---------------------------------------------------------------------------
# Agent-as-Tool
# ---------------------------------------------------------------------------


@tool
def workflow_agent(query: str, context: str) -> str:
    """
    Schedule automotive appointments and initiate service workflows.

    Use this for BUSINESS_WORKFLOW requests: service appointments, recall repairs,
    showroom consultations, test drives, or any request that triggers a booking
    or business process.

    Args:
        query:   The customer's request (verbatim — preserve dates, times, and
                 any vehicle or dealership details they mentioned).
        context: Customer ID, vehicle VIN, model, year, preferred dealership,
                 and conversation history.  Richer context means fewer missing params.

    Returns:
        JSON string with keys: action_taken, status, workflow_id, message,
        and optionally missing_params.
    """
    gateway_url = os.environ["GATEWAY_MCP_URL"]
    token = _token_cache.get()

    # Connect to AgentCore Gateway over MCP Streamable HTTP.
    # The gateway exposes all registered Lambda/OpenAPI targets as MCP tools.
    # The agent discovers available tools at connection time — no hard-coded ARNs.
    gateway_client = MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    prompt = (
        f"Customer context:\n{context}\n\n"
        f"Customer request:\n{query}\n\n"
        "Extract the required parameters and call the appropriate workflow tool. "
        "Return your result as JSON per the format in your system prompt."
    )

    # Pass the MCP client directly — Strands manages the connection lifecycle.
    agent = Agent(
        model=HAIKU,
        system_prompt=WORKFLOW_PROMPT,
        tools=[gateway_client],
        callback_handler=None,
        trace_attributes={"gen_ai.agent.name": "workflow"},
    )

    response = agent(prompt)
    return str(response)
