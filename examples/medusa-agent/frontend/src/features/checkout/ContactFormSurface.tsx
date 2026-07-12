import {
  useCallback,
  useState,
  type FormEvent,
} from "react";
import {
  RouteDeckError,
  RouteDeckPrivateForm,
  useRouteDeckStore,
  type RouteDeckPrivateFormBinding,
  type RouteDeckSurfaceComponentProps,
} from "@routedeck/react";
import {
  RouteDeckStateError,
  type JsonObject,
  type JsonValue,
} from "@routedeck/core";

type BillingChoice = "same_as_shipping" | "separate";

interface ContactSurfaceProjection {
  formHandle: string;
  revision: number;
  complete: boolean;
  fields: string[];
  billingChoices: BillingChoice[];
  defaultBillingChoice: BillingChoice;
  countryChoices: string[];
  defaultCountryCode: string;
}

interface ContactAddressDraft {
  first_name: string;
  last_name: string;
  address_1: string;
  address_2: string;
  company: string;
  postal_code: string;
  city: string;
  country_code: string;
  province: string;
  phone: string;
}

interface ContactDraft {
  email: string;
  shipping_address: ContactAddressDraft;
  billing_choice: BillingChoice;
  billing_address: ContactAddressDraft;
}

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
      <RouteDeckError code="contact_draft_load_failed" message={binding.error.message} />
    );
  }
  return (
    <ContactEditor
      key={`${binding.snapshot.form_id}:${binding.snapshot.revision}`}
      binding={binding}
      projection={projection}
      initialDraft={decodePrivateDraft(
        binding.snapshot.value,
        projection,
      )}
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
    await dispatchAffordance("save_contact", {
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
        const form = new FormData(event.currentTarget);
        const value = contactValueFromForm(form, billingChoice);
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
    [
      binding,
      billingChoice,
      continueAfterSave,
      submitting,
    ],
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

      <AddressFields
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
        <AddressFields
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

function AddressFields({
  prefix,
  title,
  initial,
  countryChoices,
  disabled = false,
}: {
  prefix: "shipping" | "billing";
  title: string;
  initial: ContactAddressDraft;
  countryChoices: readonly string[];
  disabled?: boolean;
}) {
  const name = (field: keyof ContactAddressDraft) => `${prefix}_${field}`;
  return (
    <fieldset disabled={disabled}>
      <legend>{title}</legend>
      <label>
        First name
        <input
          name={name("first_name")}
          autoComplete={`${prefix} given-name`}
          defaultValue={initial.first_name}
          required
          maxLength={80}
        />
      </label>
      <label>
        Last name
        <input
          name={name("last_name")}
          autoComplete={`${prefix} family-name`}
          defaultValue={initial.last_name}
          required
          maxLength={80}
        />
      </label>
      <label>
        Address line 1
        <input
          name={name("address_1")}
          autoComplete={`${prefix} address-line1`}
          defaultValue={initial.address_1}
          required
          maxLength={200}
        />
      </label>
      <label>
        Address line 2
        <input
          name={name("address_2")}
          autoComplete={`${prefix} address-line2`}
          defaultValue={initial.address_2}
          maxLength={200}
        />
      </label>
      <label>
        Company
        <input
          name={name("company")}
          autoComplete={`${prefix} organization`}
          defaultValue={initial.company}
          maxLength={120}
        />
      </label>
      <label>
        City
        <input
          name={name("city")}
          autoComplete={`${prefix} address-level2`}
          defaultValue={initial.city}
          required
          maxLength={120}
        />
      </label>
      <label>
        Province or state
        <input
          name={name("province")}
          autoComplete={`${prefix} address-level1`}
          defaultValue={initial.province}
          maxLength={120}
        />
      </label>
      <label>
        Postal code
        <input
          name={name("postal_code")}
          autoComplete={`${prefix} postal-code`}
          defaultValue={initial.postal_code}
          required
          maxLength={32}
        />
      </label>
      <label>
        Country
        <select
          name={name("country_code")}
          autoComplete={`${prefix} country`}
          defaultValue={initial.country_code}
          required
        >
          {countryChoices.map((countryCode) => (
            <option key={countryCode} value={countryCode}>
              {countryCode.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <label>
        Phone
        <input
          name={name("phone")}
          type="tel"
          autoComplete={`${prefix} tel`}
          defaultValue={initial.phone}
          maxLength={32}
        />
      </label>
    </fieldset>
  );
}

function contactValueFromForm(
  form: FormData,
  billingChoice: BillingChoice,
): JsonObject {
  return {
    email: requiredFormValue(form, "email"),
    shipping_address: addressValueFromForm(form, "shipping"),
    billing_choice: billingChoice,
    ...(billingChoice === "separate"
      ? { billing_address: addressValueFromForm(form, "billing") }
      : {}),
  };
}

function addressValueFromForm(
  form: FormData,
  prefix: "shipping" | "billing",
): JsonObject {
  const field = (name: keyof ContactAddressDraft) => `${prefix}_${name}`;
  const optional = (name: keyof ContactAddressDraft) => {
    const value = optionalFormValue(form, field(name));
    return value === null ? {} : { [name]: value };
  };
  return {
    first_name: requiredFormValue(form, field("first_name")),
    last_name: requiredFormValue(form, field("last_name")),
    address_1: requiredFormValue(form, field("address_1")),
    ...optional("address_2"),
    ...optional("company"),
    postal_code: requiredFormValue(form, field("postal_code")),
    city: requiredFormValue(form, field("city")),
    country_code: requiredFormValue(form, field("country_code")),
    ...optional("province"),
    ...optional("phone"),
  };
}

function requiredFormValue(form: FormData, name: string): string {
  const value = form.get(name);
  if (typeof value !== "string" || value.length === 0) {
    throw new RouteDeckStateError(
      "private_contact_field_required",
      `Private contact field ${name} is required.`,
    );
  }
  return value;
}

function optionalFormValue(form: FormData, name: string): string | null {
  const value = form.get(name);
  if (value === null || value === "") return null;
  if (typeof value !== "string") {
    throw new RouteDeckStateError(
      "private_contact_field_invalid",
      `Private contact field ${name} is invalid.`,
    );
  }
  return value;
}

function decodeContactProjection(
  props: RouteDeckSurfaceComponentProps["props"],
): ContactSurfaceProjection {
  exactKeys(props, "$.checkout.contact_form", [
    "form_handle",
    "revision",
    "complete",
    "fields",
    "billing_choices",
    "default_billing_choice",
    "country_choices",
    "default_country_code",
  ]);
  const billingChoices = stringArray(
    props.billing_choices,
    "$.checkout.contact_form.billing_choices",
  ).map((choice) => {
    if (choice !== "same_as_shipping" && choice !== "separate") {
      invalid("$.checkout.contact_form.billing_choices", "contains an invalid choice");
    }
    return choice;
  });
  if (billingChoices.length === 0) {
    invalid("$.checkout.contact_form.billing_choices", "must not be empty");
  }
  if (new Set(billingChoices).size !== billingChoices.length) {
    invalid("$.checkout.contact_form.billing_choices", "must be unique");
  }
  const defaultBillingChoice = billingChoiceValue(
    props.default_billing_choice,
    "$.checkout.contact_form.default_billing_choice",
  );
  if (!billingChoices.includes(defaultBillingChoice)) {
    invalid(
      "$.checkout.contact_form.default_billing_choice",
      "must be one of the declared choices",
    );
  }
  const countryChoices = stringArray(
    props.country_choices,
    "$.checkout.contact_form.country_choices",
  );
  if (countryChoices.length === 0) {
    invalid("$.checkout.contact_form.country_choices", "must not be empty");
  }
  if (new Set(countryChoices).size !== countryChoices.length) {
    invalid("$.checkout.contact_form.country_choices", "must be unique");
  }
  countryChoices.forEach((countryCode, index) =>
    requireCountryCode(
      countryCode,
      `$.checkout.contact_form.country_choices[${index}]`,
    ),
  );
  const defaultCountryCode = requireCountryCode(
    props.default_country_code,
    "$.checkout.contact_form.default_country_code",
  );
  if (!countryChoices.includes(defaultCountryCode)) {
    invalid(
      "$.checkout.contact_form.default_country_code",
      "must be one of the declared choices",
    );
  }
  return {
    formHandle: stringValue(
      props.form_handle,
      "$.checkout.contact_form.form_handle",
    ),
    revision: integerValue(
      props.revision,
      "$.checkout.contact_form.revision",
      0,
    ),
    complete: booleanValue(
      props.complete,
      "$.checkout.contact_form.complete",
    ),
    fields: stringArray(props.fields, "$.checkout.contact_form.fields"),
    billingChoices,
    defaultBillingChoice,
    countryChoices,
    defaultCountryCode,
  };
}

function decodePrivateDraft(
  value: JsonObject,
  projection: ContactSurfaceProjection,
): ContactDraft {
  const shipping = optionalRecord(value.shipping_address, "$.private.shipping_address");
  const billing = optionalRecord(value.billing_address, "$.private.billing_address");
  const rawChoice = value.billing_choice;
  const choice =
    rawChoice === undefined
      ? projection.defaultBillingChoice
      : billingChoiceValue(rawChoice, "$.private.billing_choice");
  if (!projection.billingChoices.includes(choice)) {
    invalid("$.private.billing_choice", "is not currently allowed");
  }
  return {
    email: optionalDraftString(value.email, "$.private.email"),
    shipping_address: draftAddress(
      shipping,
      "$.private.shipping_address",
      projection.defaultCountryCode,
    ),
    billing_choice: choice,
    billing_address: draftAddress(
      billing,
      "$.private.billing_address",
      projection.defaultCountryCode,
    ),
  };
}

function draftAddress(
  value: Record<string, JsonValue>,
  path: string,
  defaultCountryCode: string,
): ContactAddressDraft {
  return {
    first_name: optionalDraftString(value.first_name, `${path}.first_name`),
    last_name: optionalDraftString(value.last_name, `${path}.last_name`),
    address_1: optionalDraftString(value.address_1, `${path}.address_1`),
    address_2: optionalDraftString(value.address_2, `${path}.address_2`),
    company: optionalDraftString(value.company, `${path}.company`),
    postal_code: optionalDraftString(value.postal_code, `${path}.postal_code`),
    city: optionalDraftString(value.city, `${path}.city`),
    country_code:
      value.country_code === undefined
        ? defaultCountryCode
        : requireCountryCode(value.country_code, `${path}.country_code`),
    province: optionalDraftString(value.province, `${path}.province`),
    phone: optionalDraftString(value.phone, `${path}.phone`),
  };
}

function optionalDraftString(value: JsonValue | undefined, path: string): string {
  return value === undefined ? "" : stringValue(value, path, true);
}

function optionalRecord(
  value: JsonValue | undefined,
  path: string,
): Record<string, JsonValue> {
  if (value === undefined) return {};
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(path, "must be an object");
  }
  return value as Record<string, JsonValue>;
}

function exactKeys(
  value: Readonly<Record<string, JsonValue>>,
  path: string,
  allowed: readonly string[],
): void {
  const allowlist = new Set(allowed);
  const extra = Object.keys(value).find((key) => !allowlist.has(key));
  if (extra !== undefined) invalid(path, `contains undeclared field ${extra}`);
}

function stringValue(
  value: JsonValue | undefined,
  path: string,
  allowEmpty = false,
): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    invalid(path, "must be a string");
  }
  return value;
}

function stringArray(value: JsonValue | undefined, path: string): string[] {
  if (!Array.isArray(value)) invalid(path, "must be an array");
  return value.map((item, index) => stringValue(item, `${path}[${index}]`));
}

function billingChoiceValue(
  value: JsonValue | undefined,
  path: string,
): BillingChoice {
  const choice = stringValue(value, path);
  if (choice !== "same_as_shipping" && choice !== "separate") {
    invalid(path, "is invalid");
  }
  return choice;
}

function requireCountryCode(
  value: JsonValue | undefined,
  path: string,
): string {
  const countryCode = stringValue(value, path);
  if (countryCode.length !== 2) invalid(path, "must have length 2");
  for (const character of countryCode) {
    const code = character.charCodeAt(0);
    if (code < 97 || code > 122) {
      invalid(path, "must contain two lowercase ASCII letters");
    }
  }
  return countryCode;
}

function integerValue(
  value: JsonValue | undefined,
  path: string,
  minimum: number,
): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < minimum) {
    invalid(path, "must be a valid integer");
  }
  return value;
}

function booleanValue(value: JsonValue | undefined, path: string): boolean {
  if (typeof value !== "boolean") invalid(path, "must be a boolean");
  return value;
}

function invalid(path: string, message: string): never {
  throw new RouteDeckStateError(
    "checkout_projection_invalid",
    `Checkout projection ${path} ${message}.`,
  );
}
