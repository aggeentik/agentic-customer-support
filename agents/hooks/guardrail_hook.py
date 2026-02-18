"""
GuardrailHook — Bedrock Guardrails content filtering.

Attaches to the Supervisor Agent.  Applies Bedrock Guardrails to tool call
results (AfterToolCallEvent) before they are fed back to the Supervisor model,
redacting PII and blocking denied topics.

If a guardrail blocks content the hook replaces the offending text with a
safe placeholder so the pipeline can still return a structured response.

Environment variables required:
  BEDROCK_GUARDRAIL_ID       — Guardrail resource ID
  BEDROCK_GUARDRAIL_VERSION  — Guardrail version (default: "DRAFT")
  AWS_REGION                 — used by boto3 automatically

If BEDROCK_GUARDRAIL_ID is not set the hook registers no callbacks (no-op).
This lets you run locally without a guardrail configured.
"""

from __future__ import annotations

import os

import boto3
from strands.hooks import (
    AfterToolCallEvent,
    HookProvider,
    HookRegistry,
)

_BLOCKED_PLACEHOLDER = "[CONTENT BLOCKED BY GUARDRAILS]"


class GuardrailHook(HookProvider):
    """Apply Bedrock Guardrails to tool outputs before they reach the model."""

    def __init__(
        self,
        guardrail_id: str | None = None,
        guardrail_version: str | None = None,
        region: str | None = None,
    ) -> None:
        self._guardrail_id = guardrail_id or os.environ.get("BEDROCK_GUARDRAIL_ID")
        self._guardrail_version = (
            guardrail_version
            or os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
        )
        self._client = boto3.client("bedrock-runtime", region_name=region)

    # ------------------------------------------------------------------
    # HookProvider interface
    # ------------------------------------------------------------------

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:  # type: ignore[override]
        if not self._guardrail_id:
            return  # No-op when guardrail is not configured

        # Screen sub-agent tool results before they reach the Supervisor model
        registry.add_callback(AfterToolCallEvent, self._screen_tool_result)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _screen_tool_result(self, event: AfterToolCallEvent) -> None:
        """Redact PII / blocked content in sub-agent tool results."""
        try:
            content_blocks = event.result.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    raw_text = block.get("text", "")
                    if raw_text:
                        cleaned = self._apply_guardrail(raw_text)
                        if cleaned is not None:
                            block["text"] = cleaned
        except Exception as exc:  # noqa: BLE001
            print(f"[GuardrailHook] WARNING: tool-result screening failed: {exc}")

    # ------------------------------------------------------------------
    # Bedrock Guardrails API call
    # ------------------------------------------------------------------

    def _apply_guardrail(self, text: str) -> str | None:
        """
        Call bedrock-runtime:ApplyGuardrail on OUTPUT content.

        Returns:
            Cleaned text (PII redacted) if content passes guardrail.
            _BLOCKED_PLACEHOLDER if the content is blocked.
            None on API failure (fail-open — don't break the pipeline).
        """
        try:
            response = self._client.apply_guardrail(
                guardrailIdentifier=self._guardrail_id,
                guardrailVersion=self._guardrail_version,
                source="OUTPUT",
                content=[{"text": {"text": text}}],
            )

            if response.get("action") == "GUARDRAIL_INTERVENED":
                outputs = response.get("output", [])
                if outputs:
                    # Bedrock returns the redacted/filtered version in output[0]
                    return outputs[0].get("text", {}).get("text", _BLOCKED_PLACEHOLDER)
                return _BLOCKED_PLACEHOLDER

            return text  # action == "NONE" — content is clean

        except Exception as exc:  # noqa: BLE001
            print(f"[GuardrailHook] WARNING: apply_guardrail API call failed: {exc}")
            return None  # fail-open
