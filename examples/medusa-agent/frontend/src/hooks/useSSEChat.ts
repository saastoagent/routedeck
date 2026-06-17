import { useCallback, useRef, useState } from "react";

type Role = "user" | "assistant";

export const THINKING_PLACEHOLDER = "Checking current shopping context...";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  timestampLabel: string;
  isStreaming?: boolean;
}

export interface ParsedSSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface RouteContextPayload {
  path: string;
  surface_id: string;
}

export function parseSSEFrames(
  chunk: string,
  existingBuffer: string,
): { events: ParsedSSEEvent[]; buffer: string } {
  const combined = existingBuffer + chunk;
  const frames = combined.split("\n\n");
  const buffer = frames.pop() ?? "";
  const events: ParsedSSEEvent[] = [];

  for (const frame of frames) {
    if (!frame.trim() || frame.startsWith(":")) continue;

    let event = "";
    let data: Record<string, unknown> = {};

    for (const line of frame.split("\n")) {
      if (line.startsWith("event: ")) {
        event = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        data = JSON.parse(line.slice(6));
      }
    }

    if (event) {
      events.push({ event, data });
    }
  }

  return { events, buffer };
}

export function useSSEChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const bufferRef = useRef("");
  const cursorRef = useRef(0);
  const assistantContentRef = useRef("");

  const updateAssistant = useCallback((content: string, isStreamingNow: boolean) => {
    setMessages((current) => {
      const last = current[current.length - 1];
      if (!last || last.role !== "assistant") return current;
      return [
        ...current.slice(0, -1),
        {
          ...last,
          content,
          isStreaming: isStreamingNow,
        },
      ];
    });
  }, []);

  const finishStream = useCallback(() => {
    updateAssistant(assistantContentRef.current || "The shopping assistant did not return a response.", false);
    setIsStreaming(false);
    xhrRef.current = null;
  }, [updateAssistant]);

  const handleEvent = useCallback(
    ({ event, data }: ParsedSSEEvent) => {
      if (event === "stream_start") {
        const nextConversationId = data.conversation_id;
        if (typeof nextConversationId === "string") {
          setConversationId(nextConversationId);
        }
        return;
      }

      if (event === "message_delta") {
        const content = data.content;
        if (typeof content === "string") {
          assistantContentRef.current += content;
          updateAssistant(assistantContentRef.current, true);
        }
        return;
      }

      if (event === "error") {
        const message =
          typeof data.message === "string"
            ? data.message
            : "The shopping assistant could not respond.";
        assistantContentRef.current = message;
        updateAssistant(message, false);
        setIsStreaming(false);
        return;
      }

      if (event === "stream_end") {
        finishStream();
      }
    },
    [finishStream, updateAssistant],
  );

  const parseProgress = useCallback(
    (responseText: string) => {
      const nextChunk = responseText.slice(cursorRef.current);
      cursorRef.current = responseText.length;
      const parsed = parseSSEFrames(nextChunk, bufferRef.current);
      bufferRef.current = parsed.buffer;
      parsed.events.forEach(handleEvent);
    },
    [handleEvent],
  );

  const sendMessage = useCallback(
    (message: string, routeContext?: RouteContextPayload) => {
      const trimmed = message.trim();
      if (!trimmed || isStreaming) return;
      const nextConversationId = conversationId ?? crypto.randomUUID();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        timestampLabel: formatTimestamp(),
      };
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: THINKING_PLACEHOLDER,
        timestampLabel: formatTimestamp(),
        isStreaming: true,
      };

      setMessages((current) => [...current, userMessage, assistantMessage]);
      setConversationId(nextConversationId);
      setIsStreaming(true);
      assistantContentRef.current = "";
      bufferRef.current = "";
      cursorRef.current = 0;

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;
      xhr.open("POST", "/api/medusa-agent/agent/stream");
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.onprogress = () => parseProgress(xhr.responseText);
      xhr.onloadend = () => {
        if (xhr.responseText.length > cursorRef.current) {
          parseProgress(xhr.responseText);
        }
        finishStream();
      };
      xhr.onerror = () => {
        assistantContentRef.current = "Connection failed. Please try again.";
        finishStream();
      };
      xhr.send(
        JSON.stringify({
          message: trimmed,
          conversation_id: nextConversationId,
          ...(routeContext ? { route_context: routeContext } : {}),
        }),
      );
    },
    [conversationId, finishStream, isStreaming, parseProgress],
  );

  return {
    messages,
    isStreaming,
    conversationId,
    sendMessage,
    clearMessages: () => {
      xhrRef.current?.abort();
      xhrRef.current = null;
      bufferRef.current = "";
      cursorRef.current = 0;
      assistantContentRef.current = "";
      setConversationId(null);
      setIsStreaming(false);
      setMessages([]);
    },
  };
}

function formatTimestamp(): string {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
