"""
streamlit_demo.py — Local CRM demo for the Automotive Customer Support agent.

Invokes the deployed AgentCore Runtime directly via boto3
(bedrock-agentcore:InvokeAgentRuntime) — no API Gateway or WAF required.

Two invocation modes selectable in the sidebar:
  • Cloud  — calls the deployed AgentCore Runtime (requires agent ARN + AWS creds)
  • Local  — posts to http://localhost:8080/invocations (for `agentcore launch --local`)

Usage:
    pip install streamlit boto3 httpx
    streamlit run streamlit_demo.py
"""

from __future__ import annotations

import json
import uuid

import boto3
import httpx
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="BMW Customer Support — AI Assistant Demo",
    page_icon="🚗",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar — configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Configuration")

    mode = st.radio(
        "Invocation mode",
        ["☁️ Cloud (AgentCore Runtime)", "💻 Local (localhost:8080)"],
        help="Cloud: calls the deployed AWS endpoint. Local: calls agentcore launch --local.",
    )

    if "Cloud" in mode:
        agent_arn = st.text_input(
            "Agent Runtime ARN",
            placeholder="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-agent-abc",
            help="Copy from agentcore deploy output or .bedrock_agentcore.yaml",
        )
        aws_region = st.text_input("AWS Region", value="us-east-1")
        qualifier = st.text_input("Qualifier", value="DEFAULT")
    else:
        local_url = st.text_input("Local endpoint", value="http://localhost:8080/invocations")

    st.divider()
    st.caption("**Optional vehicle context**")
    meta_vin = st.text_input("VIN", placeholder="WBA12345678901234")
    meta_model = st.text_input("Model", placeholder="BMW 5 Series")
    meta_year = st.text_input("Year", placeholder="2022")
    meta_dealership = st.text_input("Preferred Dealership ID", placeholder="BMW-LONDON-001")
    meta_mileage = st.text_input("Mileage", placeholder="32000")

# ---------------------------------------------------------------------------
# Main — CRM form
# ---------------------------------------------------------------------------

st.title("🚗 BMW Customer Support — AI Response Generator")
st.caption(
    "Human agents use this tool to generate a suggested reply. "
    "The AI response is always reviewed before sending to the customer."
)

col_left, col_right = st.columns([2, 1])

with col_left:
    customer_query = st.text_area(
        "Customer query",
        placeholder=(
            "e.g. What does the orange triangle warning light mean on my dashboard?\n"
            "     I'd like to book a service appointment for an oil change."
        ),
        height=120,
    )

with col_right:
    customer_id = st.text_input("Customer ID", placeholder="CUST-00123")
    ticket_id = st.text_input("Ticket ID", placeholder="TKT-4567")

generate = st.button("✨ Generate AI Response", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_payload() -> dict:
    metadata: dict = {}
    if meta_vin:
        metadata["vehicle_vin"] = meta_vin
    if meta_model:
        metadata["model"] = meta_model
    if meta_year:
        metadata["year"] = meta_year
    if meta_dealership:
        metadata["dealership_id"] = meta_dealership
    if meta_mileage:
        metadata["mileage"] = meta_mileage

    return {
        "customer_query": customer_query,
        **({"customer_id": customer_id} if customer_id else {}),
        **({"ticket_id": ticket_id} if ticket_id else {}),
        **({"metadata": metadata} if metadata else {}),
    }


def _invoke_cloud(payload: dict) -> dict:
    client = boto3.client("bedrock-agentcore", region_name=aws_region)
    raw = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload).encode(),
        qualifier=qualifier,
    )
    chunks = [chunk.decode("utf-8") for chunk in raw.get("response", [])]
    return json.loads("".join(chunks))


def _invoke_local(payload: dict) -> dict:
    resp = httpx.post(
        local_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _render_response(result: dict) -> None:
    request_type = result.get("request_type", "UNKNOWN")
    classification = result.get("classification", "—")
    confidence = result.get("confidence", 0.0)
    escalation = result.get("escalation_needed", False)
    response_text = result.get("response", "")
    sources = result.get("sources", [])
    workflow_actions = result.get("workflow_actions", [])

    # --- Header badges ---
    badge_color = {
        "INFORMATIONAL": "blue",
        "BUSINESS_WORKFLOW": "green",
        "UNKNOWN": "red",
    }.get(request_type, "gray")

    col1, col2, col3 = st.columns(3)
    col1.metric("Request type", request_type)
    col2.metric("Classification", classification)
    col3.metric("Confidence", f"{confidence:.0%}")

    if escalation:
        st.error("⚠️ **ESCALATION REQUIRED** — please review carefully before sending.")

    st.divider()

    # --- Suggested reply ---
    st.subheader("💬 Suggested reply")
    st.info(response_text)

    # --- Sources ---
    if sources:
        st.subheader("📚 Sources")
        for i, src in enumerate(sources, 1):
            with st.expander(f"Source {i} — score {src.get('score', 0):.2f} — {src.get('uri', '')}"):
                st.write(src.get("text", ""))

    # --- Workflow actions ---
    if workflow_actions:
        st.subheader("⚙️ Workflow actions")
        for action in workflow_actions:
            status = action.get("status", "")
            icon = {"COMPLETED": "✅", "INITIATED": "🔄", "FAILED": "❌", "MISSING_PARAMS": "⚠️"}.get(status, "ℹ️")
            with st.expander(f"{icon} {action.get('action', '—')} — {status}"):
                if wf_id := action.get("workflow_id"):
                    st.write(f"**Workflow ID:** {wf_id}")
                st.write(action.get("message", ""))

    # --- Raw JSON (collapsed) ---
    with st.expander("🔍 Raw JSON response"):
        st.json(result)


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------

if generate:
    if not customer_query.strip():
        st.warning("Please enter a customer query.")
        st.stop()

    if "Cloud" in mode and not agent_arn:
        st.error("Please enter the Agent Runtime ARN in the sidebar.")
        st.stop()

    payload = _build_payload()

    with st.spinner("Calling AI agents…"):
        try:
            if "Cloud" in mode:
                result = _invoke_cloud(payload)
            else:
                result = _invoke_local(payload)
        except Exception as exc:
            st.error(f"Invocation failed: {exc}")
            st.stop()

    _render_response(result)
