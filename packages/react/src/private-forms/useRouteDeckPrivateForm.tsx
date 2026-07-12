import { useCallback, useEffect, useRef, useState } from "react";
import {
  RouteDeckStateError,
  type JsonObject,
  type RouteDeckPrivateFormLoadOptions,
  type RouteDeckPendingPrivateFormSave,
  type RouteDeckPrivateFormSnapshot,
} from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";

export interface RouteDeckPrivateFormBinding {
  snapshot: RouteDeckPrivateFormSnapshot | null;
  pending: boolean;
  error: Error | null;
  retainedSave: RouteDeckPendingPrivateFormSave | null;
  load(
    options?: RouteDeckPrivateFormLoadOptions,
  ): Promise<RouteDeckPrivateFormSnapshot>;
  retrySave(): Promise<RouteDeckPrivateFormSnapshot>;
  abandonSave(): Promise<void>;
  save(
    value: JsonObject,
    options?: { complete?: boolean },
  ): Promise<RouteDeckPrivateFormSnapshot>;
  clear(): void;
}

export function useRouteDeckPrivateForm(
  formId: string,
  options: { loadOnMount?: boolean } = {},
): RouteDeckPrivateFormBinding {
  const { privateForms, store, createRequestId } = useRouteDeckRuntime();
  const [snapshot, setSnapshot] = useState<RouteDeckPrivateFormSnapshot | null>(
    () => privateForms?.get(formId) ?? null,
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const loadSequence = useRef(0);

  const requireForms = useCallback(() => {
    if (privateForms === null) {
      throw new RouteDeckStateError(
        "private_form_state_required",
        "RouteDeck private-form hooks require an in-memory private-form state.",
      );
    }
    return privateForms;
  }, [privateForms]);

  const load = useCallback(async (loadOptions: RouteDeckPrivateFormLoadOptions = {}) => {
    const sequence = ++loadSequence.current;
    setPending(true);
    setError(null);
    try {
      const loaded = await requireForms().load(formId, loadOptions);
      loadOptions.signal?.throwIfAborted();
      if (loadSequence.current === sequence) setSnapshot(loaded);
      return loaded;
    } catch (caught) {
      if (isAbortError(caught)) throw caught;
      const resolved = asError(caught);
      if (loadSequence.current === sequence) setError(resolved);
      throw resolved;
    } finally {
      if (loadSequence.current === sequence) setPending(false);
    }
  }, [formId, requireForms]);

  const save = useCallback(
    async (value: JsonObject, saveOptions: { complete?: boolean } = {}) => {
      const sessionVersion = store.getState().sessionVersion;
      if (sessionVersion === null) {
        throw new RouteDeckStateError(
          "store_not_ready",
          "Saving a RouteDeck private form requires a session version.",
        );
      }
      setPending(true);
      setError(null);
      try {
        const saved = await requireForms().save(formId, {
          request_id: createRequestId(),
          expected_session_version: sessionVersion,
          value,
          ...(saveOptions.complete === undefined
            ? {}
            : { complete: saveOptions.complete }),
        });
        setSnapshot(saved);
        return saved;
      } catch (caught) {
        const resolved = asError(caught);
        setError(resolved);
        throw resolved;
      } finally {
        setPending(false);
      }
    },
    [store, formId, requireForms, createRequestId],
  );

  const clear = useCallback(() => {
    requireForms().clear(formId);
    setSnapshot(null);
    setError(null);
  }, [formId, requireForms]);

  const retrySave = useCallback(async () => {
    const forms = requireForms();
    const retained = forms.getPendingSave();
    if (retained === null || retained.formId !== formId) {
      throw new RouteDeckStateError(
        "private_form_save_retry_missing",
        `There is no retained save for private form ${formId}.`,
      );
    }
    setPending(true);
    setError(null);
    try {
      const saved = await forms.retrySave();
      setSnapshot(saved);
      return saved;
    } catch (caught) {
      const resolved = asError(caught);
      setError(resolved);
      throw resolved;
    } finally {
      setPending(false);
    }
  }, [formId, requireForms]);

  const abandonSave = useCallback(async () => {
    const forms = requireForms();
    const retained = forms.getPendingSave();
    if (retained === null || retained.formId !== formId) {
      throw new RouteDeckStateError(
        "private_form_save_retry_missing",
        `There is no retained save for private form ${formId}.`,
      );
    }
    setPending(true);
    setError(null);
    try {
      await store.resync();
      forms.abandonPendingSave();
    } catch (caught) {
      const resolved = asError(caught);
      setError(resolved);
      throw resolved;
    } finally {
      setPending(false);
    }
  }, [formId, requireForms, store]);

  useEffect(() => {
    if (!options.loadOnMount) return;
    const usableSnapshot =
      snapshot?.form_id === formId
        ? snapshot
        : (privateForms?.get(formId) ?? null);
    if (usableSnapshot !== null) {
      if (snapshot !== usableSnapshot) setSnapshot(usableSnapshot);
      setError(null);
      return;
    }
    const controller = new AbortController();
    void load({ signal: controller.signal }).catch((caught: unknown) => {
      if (isAbortError(caught)) return;
    });
    return () => controller.abort();
  }, [formId, load, options.loadOnMount, privateForms, snapshot]);

  return {
    snapshot: snapshot?.form_id === formId ? snapshot : null,
    pending,
    error,
    retainedSave: (() => {
      const retained = privateForms?.getPendingSave() ?? null;
      return retained?.formId === formId ? retained : null;
    })(),
    load,
    save,
    retrySave,
    abandonSave,
    clear,
  };
}

function isAbortError(value: unknown): value is Error {
  return value instanceof Error && value.name === "AbortError";
}

function asError(value: unknown): Error {
  return value instanceof Error
    ? value
    : new Error("The RouteDeck private-form operation failed.");
}
