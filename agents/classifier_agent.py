"""
Classifier Agent — intent routing.

Model  : Claude Haiku 4.5  (fast, cheap, no tools needed)
Role   : Classify the customer query as INFORMATIONAL or BUSINESS_WORKFLOW.
Tools  : None — pure text classification.
Output : "CLASSIFICATION: <reason>" — parsed by the Supervisor.
"""

from strands import Agent, tool

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CLASSIFIER_PROMPT = """\
You are an intent classifier for an automotive manufacturer customer support system.

Classify the customer query into exactly one of:

  INFORMATIONAL  — The customer is asking a question about their vehicle or a vehicle
                   they are considering purchasing.
                   Examples: how a feature works, what a warning light means, vehicle
                   specifications, fuel range, driver assistance systems, infotainment,
                   safety ratings, comparing trim levels, towing capacity.

  BUSINESS_WORKFLOW — The customer is requesting that an action be scheduled or initiated.
                      Examples: book a service appointment, schedule a showroom visit,
                      arrange a test drive, initiate a warranty claim, request roadside
                      assistance, register a vehicle, book a recall repair.

Rules:
- Reply with ONLY one line in this exact format:
    <CLASSIFICATION>: <one-sentence reason>
- Classification must be uppercase.
- Do not add any other text, greetings, or explanation.

Examples:
  Q: "What does the orange triangle warning light mean?"
  A: INFORMATIONAL: Customer asking about the meaning of a dashboard warning indicator.

  Q: "I'd like to book a service appointment for my oil change."
  A: BUSINESS_WORKFLOW: Customer requesting to schedule a vehicle service appointment.

  Q: "How does the adaptive cruise control work?"
  A: INFORMATIONAL: Customer asking about the functionality of a driver assistance feature.

  Q: "Can I come in to test drive the new X5?"
  A: BUSINESS_WORKFLOW: Customer requesting to schedule a test drive appointment.

  Q: "What is the maximum towing capacity of the 5 Series?"
  A: INFORMATIONAL: Customer asking about vehicle specification.

  Q: "I want to speak to a sales advisor about buying a new car."
  A: BUSINESS_WORKFLOW: Customer requesting a showroom consultation appointment.
"""

# ---------------------------------------------------------------------------
# Agent-as-Tool
# ---------------------------------------------------------------------------


@tool
def classifier_agent(query: str, context: str) -> str:
    """
    Classify an automotive customer support query as INFORMATIONAL or BUSINESS_WORKFLOW.

    Call this first for every request to determine how to route it.

    Args:
        query:   The customer's question or request (latest message only).
        context: Relevant context — customer ID, vehicle VIN, conversation history.
                 Pass as a plain text string.

    Returns:
        A single line: "<CLASSIFICATION>: <reason>".
        Classification is either INFORMATIONAL or BUSINESS_WORKFLOW.
    """
    agent = Agent(
        model=HAIKU,
        system_prompt=CLASSIFIER_PROMPT,
        callback_handler=None,  # suppress intermediate stdout
    )

    response = agent(f"Context:\n{context}\n\nCustomer query:\n{query}")
    return str(response)
