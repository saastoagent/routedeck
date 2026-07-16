import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { AssistantMarkdown } from "../ui/AssistantMarkdown";

afterEach(cleanup);

it("renders useful assistant Markdown without enabling raw HTML", () => {
  const rendered = render(
    <AssistantMarkdown>{`## A concise answer

- First choice
- Second choice

| Size | Stock |
| --- | --- |
| M | Available |

Use \`quantity\` or:

\`\`\`ts
const quantity = 2;
\`\`\`

<strong>Raw HTML stays text</strong>`}</AssistantMarkdown>,
  );

  expect(
    rendered.getByRole("heading", { level: 2, name: "A concise answer" }),
  ).toBeVisible();
  expect(rendered.getByRole("list")).toBeVisible();
  expect(rendered.getByRole("table")).toBeVisible();
  expect(rendered.getByText("quantity")).toBeVisible();
  expect(rendered.getByText("const quantity = 2;")).toBeVisible();
  expect(rendered.container).toHaveTextContent(
    "<strong>Raw HTML stays text</strong>",
  );
  expect(rendered.container.querySelector("strong")).toBeNull();
});

it("keeps local links in context and isolates external links", () => {
  const rendered = render(
    <AssistantMarkdown>{`[Open product](/products/t-shirt)

[Read Medusa](https://docs.medusajs.com/)

[Unsafe](javascript:alert('nope'))`}</AssistantMarkdown>,
  );

  expect(rendered.getByRole("link", { name: "Open product" })).toMatchObject({
    target: "",
    rel: "",
  });
  expect(rendered.getByRole("link", { name: "Read Medusa" })).toMatchObject({
    target: "_blank",
    rel: "noopener noreferrer",
  });
  expect(rendered.queryByRole("link", { name: "Unsafe" })).toBeNull();
  expect(rendered.getByText("Unsafe").tagName).toBe("SPAN");
});
