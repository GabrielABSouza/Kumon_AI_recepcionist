Executive Summary

- Single orchestrator: CeciliaWorkflow.
- Smart routing: SmartRouter = Intent + PatternScorer + Stage → ThresholdEngine.
- Scope: From sanitized message → state update → router decision → return RoutingDecision to CeciliaWorkflow.

Decisions

- Orchestrator: Use CeciliaWorkflow only.
- Preprocessing boundary: MessagePreprocessor runs in API before orchestrator.
- Routing: Conditional edges call SmartRouter.decide(state) to determine next node.
- Confidence model: Combine Intent confidence and Pattern score, modulated by Stage, via ThresholdEngine.

Scope

- From sanitized user_message entry into CeciliaWorkflow to SmartRouter’s RoutingDecision returned to the workflow (no
node execution/validation in this scope).

Components

- MessagePreprocessor: Sanitizes input and enforces auth/rate limits.
- CeciliaWorkflow: Orchestrates LangGraph; manages CeciliaState.
- SmartRouter: Routing decision using:
    - IntentClassifier → intent_confidence
    - PatternScorer (stage‑aware) → pattern_confidence
    - current_stage (from state) → stage multipliers/logic
    - ThresholdEngine → action, target_node, final_confidence
- IntentClassifier: Returns raw intent and intent_confidence.
- PatternScorer: Computes stage‑aware pattern_confidence via regex/keywords.
- ThresholdEngine: Combines confidences with stage multipliers/penalties; outputs ThresholdDecision.

Flow (Up to Router Decision)
- Evolution webhook → message_preprocessor.process_message(...) → sanitized message.
- CeciliaWorkflow.process_message(phone_number, user_message):
    - Load/build CeciliaState (canonical enums).
    - Append user message to state["messages"], update counters/metrics.
    - Call SmartRouter.decide(state):
    - Uses `state["last_user_message"]`, `state["current_stage"]`, `state["collected_data"]`, `metrics`.
- Save routing_info in state; end scope (return to workflow with decision).

Confidence Model

- intent_confidence: From IntentClassifier.
- pattern_confidence: From PatternScorer (stage‑aware rules):
    - Weighted regex/keywords + context/entity/recency boosts − penalties.
    - Stage multipliers (based on state.current_stage): greeting 1.2, scheduling 1.0, information 0.9 (tunable).
    - Normalize to [0,1].
- Final confidence:
    - final_confidence = w_intent*intent_confidence + w_pattern*pattern_confidence
    - Apply stage multipliers/penalties in ThresholdEngine (using current_stage).
    - Choose action (proceed/enhance/fallback/escalate) and target_node.

Contracts

- IntentResult:
    - category: str, subcategory?: str, confidence: float, context_entities: Dict[str,Any]
- PatternScores (optional diagnostics):
    - per_route: Dict[str,float], best_route: str, pattern_confidence: float
- ThresholdDecision:
    - action: "proceed"|"enhance_with_llm"|"fallback_level1"|"fallback_level2"|"escalate_human"
    - target_node:
"greeting"|"qualification"|"information"|"scheduling"|"validation"|"handoff"|"confirmation"|"completed"|"fallback"
    - final_confidence: float, rule_applied: str, reasoning: str
- RoutingDecision (SmartRouter → Workflow):
    - target_node, threshold_action, final_confidence
    - intent_confidence, pattern_confidence
    - rule_applied, reasoning, timestamp

State Expectations

- CeciliaState uses canonical enums:
    - current_stage: ConversationStage
    - current_step: ConversationStep
- CeciliaWorkflow stores router metadata:
    - state["routing_info"] = { target_node, threshold_action, final_confidence, intent_confidence, pattern_confidence,
rule_applied, reasoning, timestamp }
    - state["threshold_action"] = threshold_action
- No stage classifier: always use state["current_stage"] as the stage input for SmartRouter/Threshold.

Integration Points

- Preprocessing: Keep in app/api/evolution.py before calling CeciliaWorkflow.
- Routing hook (LangGraph edges): In each conditional edge (e.g., route_from_greeting, route_from_information, …):
    - Call SmartRouter.decide(state) (which reads current_stage from state).
    - Save routing_info to state.
    - Return decision.target_node to LangGraph.

Enum Standardization

- Replace any WorkflowStage.INFORMATION usage with ConversationStage.INFORMATION_GATHERING.
- Ensure nodes, template resolver, and edges use canonical enums and that current_stage is always present.

Telemetry

- Log: current_stage, target_node, intent_confidence, pattern_confidence, final_confidence, rule_applied,
threshold_action (plus phone tail).

Acceptance Criteria

- SmartRouter.decide(state) (with current_stage) returns deterministic RoutingDecision.
- routing_info saved in state and visible in logs.
- No references to old secure workflow in routing path.
- Enums consistent across state, edges, and template resolution.