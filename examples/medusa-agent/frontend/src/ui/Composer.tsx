import { useCallback, useState, type FormEvent } from "react";

export interface ComposerProps {
  disabled: boolean;
  onSend(message: string): Promise<void>;
  onCancel(): void;
  onRetry?: () => Promise<void>;
  onDiscardPending?: () => Promise<void>;
}

export function Composer({
  disabled,
  onSend,
  onCancel,
  onRetry,
  onDiscardPending,
}: ComposerProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<Error | null>(null);

  const submit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (disabled || onRetry !== undefined || !draft.trim()) return;
      setError(null);
      try {
        await onSend(draft);
        setDraft("");
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("The chat message could not be sent."),
        );
      }
    },
    [disabled, draft, onRetry, onSend],
  );
  const retry = useCallback(async () => {
    if (onRetry === undefined) return;
    setError(null);
    try {
      await onRetry();
      setDraft("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("The chat message could not be retried."),
      );
    }
  }, [onRetry]);
  const discard = useCallback(async () => {
    if (onDiscardPending === undefined) return;
    setError(null);
    try {
      await onDiscardPending();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("The chat request could not be abandoned safely."),
      );
    }
  }, [onDiscardPending]);

  return (
    <form onSubmit={(event) => void submit(event)} data-agent-composer="">
      <label htmlFor="medusa-agent-message">Message the buyer assistant</label>
      <textarea
        id="medusa-agent-message"
        name="message"
        value={draft}
        disabled={disabled || onRetry !== undefined}
        rows={3}
        onChange={(event) => setDraft(event.currentTarget.value)}
      />
      <div>
        {onRetry === undefined ? (
          <button type="submit" disabled={disabled || !draft.trim()}>
            Send
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={disabled}
              onClick={() => void retry()}
            >
              Retry exact message
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => void discard()}
            >
              Edit as new message
            </button>
          </>
        )}
        {disabled ? (
          <button type="button" onClick={onCancel}>
            Stop response
          </button>
        ) : null}
      </div>
      {error === null ? null : <p role="alert">{error.message}</p>}
    </form>
  );
}
