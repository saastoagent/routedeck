import { useCallback, useState, type FormEvent } from "react";
import {
  RouteDeckError,
  RouteDeckPrivateForm,
  useRouteDeckStore,
  type RouteDeckPrivateFormBinding,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";

import { ContactAddressFields } from "./ContactAddressFields";
import { CheckoutAffordanceId } from "./affordances";
import {
  contactValueFromForm,
  decodeContactProjection,
  decodePrivateDraft,
  type BillingChoice,
  type ContactDraft,
  type ContactSurfaceProjection,
} from "./contactFormModel";

export function ContactFormSurface({
  props,
  dispatchAffordance,
}: RouteDeckSurfaceComponentProps) {
  const projection = decodeContactProjection(props);
  const renderPrivateForm = useCallback(
    (binding: RouteDeckPrivateFormBinding) => (
      <ContactPrivateFormContent
        binding={binding}
        projection={projection}
        dispatchAffordance={dispatchAffordance}
      />
    ),
    [dispatchAffordance, projection],
  );

  return (
    <RouteDeckPrivateForm formId={projection.formHandle} loadOnMount>
      {renderPrivateForm}
    </RouteDeckPrivateForm>
  );
}

function ContactPrivateFormContent({
  binding,
  projection,
  dispatchAffordance,
}: {
  binding: RouteDeckPrivateFormBinding;
  projection: ContactSurfaceProjection;
  dispatchAffordance: RouteDeckSurfaceComponentProps["dispatchAffordance"];
}) {
  if (binding.snapshot === null) {
    return binding.error === null ? (
      <div role="status">Loading your private checkout draft…</div>
    ) : (
      <RouteDeckError
        code="contact_draft_load_failed"
        message={binding.error.message}
      />
    );
  }
  return (
    <ContactEditor
      key={`${binding.snapshot.form_id}:${binding.snapshot.revision}`}
      binding={binding}
      projection={projection}
      initialDraft={decodePrivateDraft(binding.snapshot.value, projection)}
      dispatchAffordance={dispatchAffordance}
    />
  );
}

function ContactEditor({
  binding,
  projection,
  initialDraft,
  dispatchAffordance,
}: {
  binding: RouteDeckPrivateFormBinding;
  projection: ContactSurfaceProjection;
  initialDraft: ContactDraft;
  dispatchAffordance: RouteDeckSurfaceComponentProps["dispatchAffordance"];
}) {
  const store = useRouteDeckStore();
  const [billingChoice, setBillingChoice] = useState<BillingChoice>(
    initialDraft.billing_choice,
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const continueAfterSave = useCallback(async () => {
    await store.resync();
    await dispatchAffordance(CheckoutAffordanceId.SaveContact, {
      form_handle: projection.formHandle,
    });
  }, [dispatchAffordance, projection.formHandle, store]);
  const submit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        const value = contactValueFromForm(
          new FormData(event.currentTarget),
          billingChoice,
        );
        await binding.save(value, { complete: true });
        await continueAfterSave();
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught
            : new Error("RouteDeck could not save the checkout contact."),
        );
      } finally {
        setSubmitting(false);
      }
    },
    [binding, billingChoice, continueAfterSave, submitting],
  );
  const retrySave = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await binding.retrySave();
      await continueAfterSave();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("RouteDeck could not retry the checkout contact save."),
      );
    } finally {
      setSubmitting(false);
    }
  }, [binding, continueAfterSave, submitting]);
  const abandonSave = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await binding.abandonSave();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught
          : new Error("RouteDeck could not abandon the checkout contact save."),
      );
    } finally {
      setSubmitting(false);
    }
  }, [binding, submitting]);

  return (
    <form
      onSubmit={submit}
      data-private-form={projection.formHandle}
      data-private-form-revision={projection.revision}
      data-private-form-fields={projection.fields.join(" ")}
    >
      <h1>Contact and delivery address</h1>
      <label>
        Email
        <input
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={initialDraft.email}
          required
          maxLength={254}
        />
      </label>

      <ContactAddressFields
        prefix="shipping"
        title="Shipping address"
        initial={initialDraft.shipping_address}
        countryChoices={projection.countryChoices}
      />

      <fieldset>
        <legend>Billing address</legend>
        {projection.billingChoices.map((choice) => (
          <label key={choice}>
            <input
              type="radio"
              name="billing_choice"
              value={choice}
              checked={billingChoice === choice}
              onChange={() => setBillingChoice(choice)}
            />
            {choice === "same_as_shipping"
              ? "Same as shipping address"
              : "Use a separate billing address"}
          </label>
        ))}
      </fieldset>

      <div hidden={billingChoice !== "separate"}>
        <ContactAddressFields
          prefix="billing"
          title="Separate billing address"
          initial={initialDraft.billing_address}
          countryChoices={projection.countryChoices}
          disabled={billingChoice !== "separate"}
        />
      </div>

      {error === null ? null : (
        <RouteDeckError code="contact_save_failed" message={error.message} />
      )}
      {binding.retainedSave === null ? (
        <button type="submit" disabled={submitting || binding.pending}>
          {submitting ? "Saving…" : "Continue to delivery"}
        </button>
      ) : (
        <div role="alert" data-private-form-save-recovery="">
          <p>The private save response was lost. Choose an explicit recovery.</p>
          <button
            type="button"
            disabled={submitting || binding.pending}
            onClick={() => void retrySave()}
          >
            Retry exact save
          </button>
          <button
            type="button"
            disabled={submitting || binding.pending}
            onClick={() => void abandonSave()}
          >
            Abandon and resync
          </button>
        </div>
      )}
    </form>
  );
}
