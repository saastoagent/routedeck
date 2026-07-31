import { useCallback, useEffect, useState, type CSSProperties } from "react";

import type { JsonObject, RouteDeckInspection } from "@routedeck/core";

import { useRouteDeckProjection } from "../hooks/projection";
import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";
import { RouteDeckNavGraph } from "./RouteDeckNavGraph";

export interface RouteDeckInspectorProps {
  initialView?: "graph" | "context";
  className?: string;
  style?: CSSProperties;
}

/** Framework-owned live NavGraph and current agent-context inspector. */
export function RouteDeckInspector({
  initialView = "graph",
  className,
  style,
}: RouteDeckInspectorProps) {
  const runtime = useRouteDeckRuntime();
  const projection = useRouteDeckProjection();
  const [view, setView] = useState<"graph" | "context">(initialView);
  const [inspection, setInspection] = useState<RouteDeckInspection | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  const loadInspection = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInspection(await runtime.store.inspect());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("The current agent context could not be inspected."),
      );
    } finally {
      setLoading(false);
    }
  }, [runtime.store]);

  useEffect(() => {
    if (view !== "context") return;
    void loadInspection();
  }, [loadInspection, projection?.projection_version, view]);

  return (
    <section
      aria-label="RouteDeck inspector"
      data-routedeck-inspector=""
      className={className}
      style={style}
    >
      <div aria-label="Navgraph view" data-navgraph-view-switcher="">
        <button
          type="button"
          aria-pressed={view === "graph"}
          onClick={() => setView("graph")}
        >
          Graph
        </button>
        <button
          type="button"
          aria-pressed={view === "context"}
          onClick={() => setView("context")}
        >
          Agent context
        </button>
      </div>
      {view === "graph" ? (
        <div data-navgraph-map="">
          <RouteDeckNavGraph />
        </div>
      ) : (
        <RouteDeckAgentContext
          inspection={inspection}
          error={error}
          loading={loading}
          onRefresh={() => void loadInspection()}
        />
      )}
    </section>
  );
}

export function RouteDeckAgentContext({
  inspection,
  error,
  loading,
  onRefresh,
}: {
  inspection: RouteDeckInspection | null;
  error: Error | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  if (loading && inspection === null) {
    return <p data-agent-context-state="">Loading current agent context…</p>;
  }
  if (error !== null) {
    return (
      <section role="alert" data-agent-context-state="">
        <strong>Agent context unavailable</strong>
        <span>{error.message}</span>
        <button type="button" onClick={onRefresh}>Retry</button>
      </section>
    );
  }
  const payload = inspection?.agent_context;
  if (payload === null || payload === undefined) {
    return (
      <section data-agent-context-state="">
        <strong>Agent context unavailable</strong>
        <p>The configured agent driver does not expose an inspection context.</p>
      </section>
    );
  }

  let parsed: ReturnType<typeof parseAgentContext>;
  try {
    parsed = parseAgentContext(payload);
  } catch (caught) {
    return (
      <section role="alert" data-agent-context-state="">
        <strong>Agent context invalid</strong>
        <span>{caught instanceof Error ? caught.message : "The inspection payload is invalid."}</span>
      </section>
    );
  }

  return (
    <section aria-label="Current agent context" data-agent-context="">
      <header>
        <div>
          <strong>Current agent context</strong>
          <small>{requireString(parsed.modelContext.current_node, "current_node")}</small>
        </div>
        <button type="button" disabled={loading} onClick={onRefresh}>Refresh</button>
      </header>

      <JsonSection title="Snapshot identity" value={parsed.snapshot} />
      <JsonSection title="Model configuration" value={parsed.model} />
      <JsonSection title="Status" value={parsed.modelContext.status} />
      <JsonSection title="Active surface" value={parsed.modelContext.active_surface} />
      <JsonSection title="Visible entities" value={parsed.modelContext.visible_entities} />
      <JsonSection title="Legal tools" value={parsed.modelContext.legal_tools} />
      <JsonSection title="Suggested actions" value={parsed.modelContext.suggested_actions} />
      <JsonSection title="Recent observations" value={parsed.modelContext.recent_observations} />
      <JsonSection title="Reconstructed messages" value={parsed.messages} />
      <JsonSection title="Effective tool definitions" value={parsed.tools} />
      <JsonSection title="Context limits" value={parsed.limits} />
      <JsonSection title="Intentional exclusions" value={parsed.exclusions} />

      <section data-agent-context-topology="">
        <h3>Navgraph diagnostics</h3>
        <JsonSection title="Reachable nodes" value={inspection?.reachable_nodes} />
        <JsonSection title="Legal operations" value={inspection?.legal_operations} />
        <JsonSection title="Blocked operations" value={inspection?.blocked_operations} />
        <JsonSection title="Guard explanations" value={inspection?.guard_explanations} />
        <JsonSection title="Capabilities" value={inspection?.capabilities} />
        <JsonSection title="Projected surfaces" value={inspection?.surfaces} />
        <JsonSection title="Route traces" value={inspection?.route_traces} />
        <JsonSection title="Runtime diagnostics" value={inspection?.diagnostics} />
      </section>

      <section data-agent-context-policies="">
        <h3>Policies in effect</h3>
        {parsed.policies.length === 0 ? <p>None.</p> : parsed.policies.map((policy) => (
          <article key={requireString(policy.policy_id, "policy_id")}>
            <strong>{requireString(policy.policy_id, "policy_id")}</strong>
            <small>
              {requireString(policy.scope, "scope")} · {requireString(policy.owner_id, "owner_id")}
            </small>
            <pre>{requireString(policy.instruction, "instruction")}</pre>
          </article>
        ))}
      </section>

      <section data-agent-context-prompt-parts="">
        <h3>Prompt composition</h3>
        <JsonSection title="Base prompt" value={parsed.promptParts.base} />
        <JsonSection title="Policy section" value={parsed.promptParts.policy_section} />
        <JsonSection title="Context section" value={parsed.promptParts.context_section} />
      </section>

      <section data-agent-context-prompt="">
        <h3>Exact system prompt</h3>
        <pre>{parsed.prompt}</pre>
      </section>
    </section>
  );
}

function JsonSection({ title, value }: { title: string; value: unknown }) {
  return (
    <details data-agent-context-section="">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function parseAgentContext(payload: JsonObject) {
  const modelContext = requireObject(payload.model_context, "model_context");
  const promptParts = requireObject(payload.prompt, "prompt");
  return {
    exclusions: requireArray(payload.intentional_exclusions, "intentional_exclusions"),
    limits: requireObject(payload.limits, "limits"),
    messages: requireObjectArray(payload.messages, "messages"),
    model: requireObject(payload.model, "model"),
    modelContext,
    policies: requireObjectArray(payload.policy_resolution, "policy_resolution"),
    prompt: requireString(promptParts.assembled, "prompt.assembled"),
    promptParts,
    snapshot: requireObject(payload.snapshot, "snapshot"),
    tools: requireObjectArray(payload.tools, "tools"),
  };
}

function requireObject(value: unknown, field: string): JsonObject {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Agent context ${field} is invalid.`);
  }
  return value as JsonObject;
}

function requireObjectArray(value: unknown, field: string): JsonObject[] {
  if (!Array.isArray(value)) throw new Error(`Agent context ${field} is invalid.`);
  return value.map((item) => requireObject(item, field));
}

function requireArray(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`Agent context ${field} is invalid.`);
  return value;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`Agent context ${field} is invalid.`);
  }
  return value;
}
