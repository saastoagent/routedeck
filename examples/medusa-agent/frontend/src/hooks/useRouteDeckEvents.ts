import { useEffect, useRef } from "react";

import { ProjectionUpdatePayload } from "./useRouteDeckProjection";

export function useRouteDeckEvents({
  conversationId,
  onProjectionUpdate,
}: {
  conversationId: string | null;
  onProjectionUpdate: (payload: ProjectionUpdatePayload) => void;
}) {
  const onProjectionUpdateRef = useRef(onProjectionUpdate);

  useEffect(() => {
    onProjectionUpdateRef.current = onProjectionUpdate;
  }, [onProjectionUpdate]);

  useEffect(() => {
    if (!conversationId || typeof EventSource === "undefined") return;

    const params = new URLSearchParams({ conversation_id: conversationId });
    const source = new EventSource(`/api/medusa-agent/route-stream?${params.toString()}`);
    const handleProjectionUpdate = (event: MessageEvent<string>) => {
      onProjectionUpdateRef.current(JSON.parse(event.data) as ProjectionUpdatePayload);
    };

    source.addEventListener("projection_update", handleProjectionUpdate);

    return () => {
      source.removeEventListener("projection_update", handleProjectionUpdate);
      source.close();
    };
  }, [conversationId]);
}
