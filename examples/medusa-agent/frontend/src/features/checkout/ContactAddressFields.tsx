import type { ContactAddressDraft } from "./contactFormModel";

export function ContactAddressFields({
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
