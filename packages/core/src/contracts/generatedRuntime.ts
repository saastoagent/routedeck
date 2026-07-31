/* eslint-disable */
/**
 * Generated from the RouteDeck Pydantic transport schema.
 * DO NOT MODIFY IT BY HAND. Run `pnpm contracts:generate`.
 */

export interface GeneratedObjectDescriptor {
  readonly required: readonly string[];
  readonly optional: readonly string[];
  readonly additionalProperties: boolean;
  readonly defaults: Readonly<Record<string, unknown>>;
}

export const generatedObjectDescriptors = Object.freeze({
  ConversationAssistantDeltaPayload: Object.freeze({
    required: Object.freeze(["content", "request_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationAssistantEndPayload: Object.freeze({
    required: Object.freeze(["projection_version", "request_id", "session_version", "turn_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationAssistantResetPayload: Object.freeze({
    required: Object.freeze(["request_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationChatErrorPayload: Object.freeze({
    required: Object.freeze(["code", "message"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationHistoryEnvelope: Object.freeze({
    required: Object.freeze(["turns"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationInputPolicy: Object.freeze({
    required: Object.freeze(["disabled_message", "enabled"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationReviewRequiredPayload: Object.freeze({
    required: Object.freeze(["expires_at", "operation_id", "review_id", "status"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationRunEnvelope: Object.freeze({
    required: Object.freeze(["run"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationRunFailurePayload: Object.freeze({
    required: Object.freeze(["code", "message"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationRunReviewPayload: Object.freeze({
    required: Object.freeze(["expires_at", "operation_id", "review_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationRunSnapshotPayload: Object.freeze({
    required: Object.freeze(["cursor", "kind", "request_id", "stage"]),
    optional: Object.freeze(["assistant_content", "failure", "projection_version", "review", "session_version", "turn_id", "user_message", "user_turn_id"]),
    additionalProperties: false,
    defaults: Object.freeze({"assistant_content": "", "failure": null, "projection_version": null, "review": null, "session_version": null, "turn_id": null, "user_message": null, "user_turn_id": null}),
  }),
  ConversationSnapshotPayload: Object.freeze({
    required: Object.freeze(["turns"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationStreamEndPayload: Object.freeze({
    required: Object.freeze(["request_id", "status"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationStreamStartPayload: Object.freeze({
    required: Object.freeze(["request_id", "session_version"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ConversationUserMessagePayload: Object.freeze({
    required: Object.freeze(["content", "request_id", "turn_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  DispatchRequest: Object.freeze({
    required: Object.freeze(["expected_session_version", "operation_id", "request_id"]),
    optional: Object.freeze(["arguments"]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  FailureEnvelope: Object.freeze({
    required: Object.freeze(["failure"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  FailureSafeDetails: Object.freeze({
    required: Object.freeze([]),
    optional: Object.freeze(["affected_capability", "delivery_phase", "http_status", "provider", "provider_code"]),
    additionalProperties: false,
    defaults: Object.freeze({"affected_capability": null, "delivery_phase": null, "http_status": null, "provider": null, "provider_code": null}),
  }),
  FrontendContract: Object.freeze({
    required: Object.freeze(["entry_node_id", "name", "nodes", "surfaces", "transitions"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  FrontendContractEnvelope: Object.freeze({
    required: Object.freeze(["frontend_contract"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  FrontendNodeContract: Object.freeze({
    required: Object.freeze(["conversation_input", "deep_link_policy", "id", "operation_ids", "route_template", "surfaces", "title"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  FrontendSurfaceContract: Object.freeze({
    required: Object.freeze(["component", "id", "lifecycle", "public_props_schema"]),
    optional: Object.freeze(["affordances"]),
    additionalProperties: false,
    defaults: Object.freeze({"affordances": []}),
  }),
  FrontendSurfaceSlots: Object.freeze({
    required: Object.freeze(["active"]),
    optional: Object.freeze(["detail", "diagnostic", "error", "form", "frame", "peer", "review", "status"]),
    additionalProperties: false,
    defaults: Object.freeze({"detail": [], "diagnostic": [], "error": [], "form": [], "frame": [], "peer": [], "review": [], "status": []}),
  }),
  FrontendTransitionContract: Object.freeze({
    required: Object.freeze(["operation_id", "outcome", "source", "target"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  InspectionPayload: Object.freeze({
    required: Object.freeze(["agent_context", "blocked_operations", "capabilities", "current_node", "diagnostics", "guard_explanations", "legal_operations", "reachable_nodes", "route_traces", "surfaces"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  OperationEvidence: Object.freeze({
    required: Object.freeze(["attempt_id", "phases", "request_fingerprint", "source"]),
    optional: Object.freeze(["delivery_phase", "result_fingerprint", "result_id"]),
    additionalProperties: false,
    defaults: Object.freeze({"delivery_phase": null, "result_fingerprint": null, "result_id": null}),
  }),
  OperationRef: Object.freeze({
    required: Object.freeze(["id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  OperationReview: Object.freeze({
    required: Object.freeze(["expires_at", "id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  PrivateFormSaved: Object.freeze({
    required: Object.freeze(["complete", "form_id", "projection_version", "revision", "session_version"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  PrivateFormSnapshot: Object.freeze({
    required: Object.freeze(["complete", "form_id", "revision", "session_version", "value"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  PrivateFormWriteRequest: Object.freeze({
    required: Object.freeze(["expected_session_version", "request_id", "value"]),
    optional: Object.freeze(["complete"]),
    additionalProperties: false,
    defaults: Object.freeze({"complete": true}),
  }),
  ProjectedNavigation: Object.freeze({
    required: Object.freeze(["can_back", "can_cancel", "can_forward", "current", "current_entry_id", "resume_handle", "route_template"]),
    optional: Object.freeze(["back_node_id", "cancel_target_node_id", "forward_node_id"]),
    additionalProperties: false,
    defaults: Object.freeze({"back_node_id": null, "cancel_target_node_id": null, "forward_node_id": null}),
  }),
  ProjectedOperation: Object.freeze({
    required: Object.freeze(["operation_id", "safety_class", "title"]),
    optional: Object.freeze(["review_required"]),
    additionalProperties: false,
    defaults: Object.freeze({"review_required": false}),
  }),
  ProjectedSuggestedAction: Object.freeze({
    required: Object.freeze(["action_id", "label", "operation_id"]),
    optional: Object.freeze(["arguments"]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ProjectedSurface: Object.freeze({
    required: Object.freeze(["component", "surface_id"]),
    optional: Object.freeze(["props"]),
    additionalProperties: false,
    defaults: Object.freeze({"props": []}),
  }),
  ProjectedSurfaceSlots: Object.freeze({
    required: Object.freeze(["active"]),
    optional: Object.freeze(["detail", "diagnostic", "error", "form", "frame", "peer", "review", "status"]),
    additionalProperties: false,
    defaults: Object.freeze({"detail": [], "diagnostic": [], "error": [], "form": [], "frame": [], "peer": [], "review": [], "status": []}),
  }),
  ProjectionDiagnostics: Object.freeze({
    required: Object.freeze(["current_node_id", "navgraph_version", "schema_version"]),
    optional: Object.freeze(["declared_provider_ids"]),
    additionalProperties: false,
    defaults: Object.freeze({"declared_provider_ids": []}),
  }),
  ProjectionLocation: Object.freeze({
    required: Object.freeze(["node_id"]),
    optional: Object.freeze(["route_params"]),
    additionalProperties: false,
    defaults: Object.freeze({"route_params": []}),
  }),
  ProjectionStatus: Object.freeze({
    required: Object.freeze([]),
    optional: Object.freeze(["code", "message"]),
    additionalProperties: false,
    defaults: Object.freeze({"code": "ready", "message": null}),
  }),
  PublicConversationTurn: Object.freeze({
    required: Object.freeze(["content", "request_id", "role", "turn_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  PublicEntityHandle: Object.freeze({
    required: Object.freeze(["entity_kind", "handle"]),
    optional: Object.freeze(["values"]),
    additionalProperties: false,
    defaults: Object.freeze({"values": []}),
  }),
  PublicEventPayload: Object.freeze({
    required: Object.freeze([]),
    optional: Object.freeze(["details", "entity_handles", "failure", "node_id", "operation_id", "request_id", "status_code"]),
    additionalProperties: false,
    defaults: Object.freeze({"details": [], "entity_handles": [], "failure": null, "node_id": null, "operation_id": null, "request_id": null, "status_code": null}),
  }),
  PublicOperationResult: Object.freeze({
    required: Object.freeze(["disposition", "evidence", "operation_id", "projection_version", "request_id", "session_version"]),
    optional: Object.freeze(["failure", "outcome", "review"]),
    additionalProperties: false,
    defaults: Object.freeze({"failure": null, "outcome": null, "review": null}),
  }),
  PublicProjection: Object.freeze({
    required: Object.freeze(["current", "diagnostics", "entities", "event_cursor", "interaction", "legal_operations", "navigation", "projection_version", "session_version", "status", "suggested_actions", "surfaces"]),
    optional: Object.freeze(["failure"]),
    additionalProperties: false,
    defaults: Object.freeze({"failure": null}),
  }),
  PublicProjectionResponse: Object.freeze({
    required: Object.freeze(["current", "diagnostics", "entities", "event_cursor", "interaction", "legal_operations", "navigation", "projection_version", "session_version", "status", "suggested_actions", "surfaces"]),
    optional: Object.freeze(["failure", "graph_node"]),
    additionalProperties: false,
    defaults: Object.freeze({"failure": null, "graph_node": null}),
  }),
  PublicRouteDeckEvent: Object.freeze({
    required: Object.freeze(["created_at", "cursor", "event_id", "event_type", "payload", "session_version"]),
    optional: Object.freeze(["projection_version"]),
    additionalProperties: false,
    defaults: Object.freeze({"projection_version": null}),
  }),
  PublicValue: Object.freeze({
    required: Object.freeze(["name", "value"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  ReviewRequest: Object.freeze({
    required: Object.freeze(["expected_session_version", "request_id"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  RouteDeckFailure: Object.freeze({
    required: Object.freeze(["code", "correlation_id", "kind", "phase", "public_message"]),
    optional: Object.freeze(["operation_id", "recovery_directive", "request_id", "safe_details"]),
    additionalProperties: false,
    defaults: Object.freeze({"operation_id": null, "recovery_directive": null, "request_id": null}),
  }),
  RouteDeckInteractionState: Object.freeze({
    required: Object.freeze([]),
    optional: Object.freeze(["owner", "phase", "request_id"]),
    additionalProperties: false,
    defaults: Object.freeze({"owner": null, "phase": "idle", "request_id": null}),
  }),
  RouteDeckTransportContracts: Object.freeze({
    required: Object.freeze(["conversation_assistant_delta", "conversation_assistant_end", "conversation_assistant_reset", "conversation_chat_error", "conversation_history", "conversation_review_required", "conversation_run_envelope", "conversation_run_failure", "conversation_run_review", "conversation_run_snapshot", "conversation_snapshot", "conversation_stream_end", "conversation_stream_start", "conversation_turn", "conversation_user_message", "dispatch_request", "event", "failure", "failure_envelope", "frontend_contract", "frontend_contract_envelope", "inspection", "operation_result", "private_form_saved", "private_form_snapshot", "private_form_write_request", "public_projection", "review_request", "session_envelope", "stream_reset"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  SessionEnvelope: Object.freeze({
    required: Object.freeze(["projection"]),
    optional: Object.freeze([]),
    additionalProperties: false,
    defaults: Object.freeze({}),
  }),
  StreamResetPayload: Object.freeze({
    required: Object.freeze(["requested_after"]),
    optional: Object.freeze(["event_type", "retained_from_cursor"]),
    additionalProperties: false,
    defaults: Object.freeze({"event_type": "stream_reset_required", "retained_from_cursor": null}),
  }),
  SurfaceAffordance: Object.freeze({
    required: Object.freeze(["event", "id"]),
    optional: Object.freeze(["operation"]),
    additionalProperties: false,
    defaults: Object.freeze({"operation": null}),
  }),
}) satisfies Readonly<Record<string, GeneratedObjectDescriptor>>;
