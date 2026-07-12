import type {
  JsonObject,
  RouteDeckPrivateFormSaved,
  RouteDeckPrivateFormSnapshot,
} from "../contracts/decode";
import type {
  RouteDeckPrivateFormClient,
  RouteDeckPrivateFormLoadOptions,
  RouteDeckPrivateFormSaveRequest,
} from "./client";
import {
  RouteDeckOutcomeUnknownError,
  RouteDeckStateError,
} from "../client/errors";
import { retainRouteDeckRequest } from "../client/retained";

export interface RouteDeckPendingPrivateFormSave {
  readonly formId: string;
  readonly requestId: string;
  readonly fingerprint: string;
}

export interface RouteDeckPrivateFormState {
  get(formId: string): RouteDeckPrivateFormSnapshot | null;
  load(
    formId: string,
    options?: RouteDeckPrivateFormLoadOptions,
  ): Promise<RouteDeckPrivateFormSnapshot>;
  save(
    formId: string,
    request: RouteDeckPrivateFormSaveRequest,
  ): Promise<RouteDeckPrivateFormSnapshot>;
  getPendingSave(): RouteDeckPendingPrivateFormSave | null;
  retrySave(): Promise<RouteDeckPrivateFormSnapshot>;
  abandonPendingSave(): void;
  clear(formId: string): void;
  dispose(): void;
}

export function createPrivateFormState(
  client: RouteDeckPrivateFormClient,
): RouteDeckPrivateFormState {
  const forms = new Map<string, RouteDeckPrivateFormSnapshot>();
  let disposed = false;
  let saveInFlight = false;
  let retainedSave: Readonly<{
    formId: string;
    request: RouteDeckPrivateFormSaveRequest;
    public: RouteDeckPendingPrivateFormSave;
  }> | null = null;
  const requireActive = () => {
    if (disposed) {
      throw new RouteDeckStateError(
        "private_form_state_disposed",
        "The RouteDeck private-form state has been disposed.",
      );
    }
  };
  const runSave = async (
    attempt: NonNullable<typeof retainedSave>,
    retrying: boolean,
  ): Promise<RouteDeckPrivateFormSnapshot> => {
    saveInFlight = true;
    try {
      const saved: RouteDeckPrivateFormSaved = await client.save(
        attempt.formId,
        attempt.request,
      );
      const snapshot: RouteDeckPrivateFormSnapshot = {
        form_id: saved.form_id,
        revision: saved.revision,
        complete: saved.complete,
        session_version: saved.session_version,
        value: attempt.request.value,
      };
      forms.set(attempt.formId, snapshot);
      if (retainedSave === attempt) retainedSave = null;
      return snapshot;
    } catch (error) {
      if (error instanceof RouteDeckOutcomeUnknownError) {
        if (error.requestId !== attempt.request.request_id) {
          throw new RouteDeckStateError(
            "private_form_save_identity_mismatch",
            "The outcome-unknown failure does not match the retained private-form save.",
          );
        }
        retainedSave = attempt;
      } else if (!retrying) {
        retainedSave = null;
      }
      throw error;
    } finally {
      saveInFlight = false;
    }
  };
  const requireSaveAvailable = () => {
    if (saveInFlight) {
      throw new RouteDeckStateError(
        "private_form_save_in_progress",
        "A RouteDeck private-form save is already in progress.",
      );
    }
    if (retainedSave !== null) {
      throw new RouteDeckStateError(
        "private_form_save_retry_required",
        "A private-form save has an unknown outcome; retry or abandon that exact request first.",
      );
    }
  };
  return {
    get(formId) {
      requireActive();
      return forms.get(formId) ?? null;
    },
    async load(formId, options = {}) {
      requireActive();
      options.signal?.throwIfAborted();
      const loaded = await client.load(formId, options);
      requireActive();
      options.signal?.throwIfAborted();
      forms.set(formId, loaded);
      return loaded;
    },
    async save(formId, request) {
      requireActive();
      requireSaveAvailable();
      const retainedRequest = retainRouteDeckRequest(request);
      const publicRequest = retainRouteDeckRequest({
        expected_session_version: request.expected_session_version,
        form_id: formId,
        value: request.value,
        ...(request.complete === undefined ? {} : { complete: request.complete }),
      });
      return runSave(
        Object.freeze({
          formId,
          request: retainedRequest.request,
          public: Object.freeze({
            formId,
            requestId: retainedRequest.request.request_id,
            fingerprint: publicRequest.fingerprint,
          }),
        }),
        false,
      );
    },
    getPendingSave() {
      requireActive();
      return retainedSave?.public ?? null;
    },
    retrySave() {
      requireActive();
      if (saveInFlight) {
        throw new RouteDeckStateError(
          "private_form_save_in_progress",
          "The retained private-form save is already being retried.",
        );
      }
      if (retainedSave === null) {
        throw new RouteDeckStateError(
          "private_form_save_retry_missing",
          "There is no outcome-unknown private-form save to retry.",
        );
      }
      return runSave(retainedSave, true);
    },
    abandonPendingSave() {
      requireActive();
      if (saveInFlight) {
        throw new RouteDeckStateError(
          "private_form_save_in_progress",
          "A private-form save cannot be abandoned while it is in progress.",
        );
      }
      retainedSave = null;
    },
    clear(formId) {
      requireActive();
      forms.delete(formId);
    },
    dispose() {
      forms.clear();
      retainedSave = null;
      disposed = true;
    },
  };
}
