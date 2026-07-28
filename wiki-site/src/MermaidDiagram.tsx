import { useEffect, useId, useState } from "react";

type DiagramState =
  | { status: "loading" }
  | { status: "rendered"; svg: string }
  | { status: "error" };

let mermaidPromise: Promise<(typeof import("mermaid"))["default"]> | undefined;

function loadMermaid() {
  mermaidPromise ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      themeVariables: {
        background: "#ffffff",
        primaryColor: "#f5f8ff",
        primaryBorderColor: "#2675ea",
        primaryTextColor: "#111827",
        secondaryColor: "#f4fbf7",
        secondaryBorderColor: "#23845b",
        secondaryTextColor: "#111827",
        tertiaryColor: "#f7f9fc",
        tertiaryBorderColor: "#8a96aa",
        lineColor: "#42526b",
        textColor: "#111827",
        mainBkg: "#ffffff",
        nodeBorder: "#2675ea",
        clusterBkg: "#fbfcfe",
        clusterBorder: "#9ba8bb",
        edgeLabelBackground: "#ffffff",
        fontSize: "15px",
      },
      flowchart: {
        htmlLabels: false,
        useMaxWidth: true,
      },
      sequence: {
        useMaxWidth: true,
      },
    });
    return mermaid;
  });
  return mermaidPromise;
}

export function MermaidDiagram({ source }: { source: string }) {
  const reactId = useId();
  const diagramId = `routedeck-diagram-${reactId.replace(/[^a-z0-9_-]/gi, "")}`;
  const normalizedSource = source.trim();
  const [state, setState] = useState<DiagramState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });

    void loadMermaid()
      .then((mermaid) => mermaid.render(diagramId, normalizedSource))
      .then(({ svg }) => {
        if (active) {
          setState({ status: "rendered", svg });
        }
      })
      .catch(() => {
        if (active) {
          setState({ status: "error" });
        }
      });

    return () => {
      active = false;
    };
  }, [diagramId, normalizedSource]);

  return (
    <figure className="diagram-frame">
      <figcaption>
        <span>Diagram</span>
        <span className="diagram-format">Mermaid</span>
      </figcaption>
      {state.status === "loading" ? (
        <div className="diagram-loading" aria-live="polite">Rendering diagram…</div>
      ) : null}
      {state.status === "rendered" ? (
        <div
          className="diagram-canvas"
          data-testid="diagram-rendered"
          role="img"
          aria-label="Rendered Mermaid diagram"
          dangerouslySetInnerHTML={{ __html: state.svg }}
        />
      ) : null}
      {state.status === "error" ? (
        <div className="diagram-error" role="alert">
          <strong>Diagram could not be rendered.</strong>
          <span>The original Mermaid source is available below.</span>
        </div>
      ) : null}
      <details className="diagram-source-details" open={state.status === "error"}>
        <summary>View Mermaid source</summary>
        <pre><code>{normalizedSource}</code></pre>
      </details>
    </figure>
  );
}
