import { expect, it } from "vitest";

import {
  decodePrivateFormSaved,
  decodePrivateFormSnapshot,
} from "./decode";

it("accepts virtual snapshot revision zero but rejects saved revision zero", () => {
  const snapshot = decodePrivateFormSnapshot({
    form_id: "form-public-1",
    revision: 0,
    complete: false,
    session_version: 1,
    value: {},
  });

  expect(snapshot.revision).toBe(0);
  expect(() =>
    decodePrivateFormSaved({
      form_id: "form-public-1",
      revision: 0,
      complete: false,
      session_version: 1,
      projection_version: 1,
    }),
  ).toThrow(/\$privateFormSaved\.revision/);
});
