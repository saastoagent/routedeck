import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { App } from "./App";

describe("RouteDeck wiki site", () => {
  afterEach(cleanup);

  beforeEach(() => {
    window.history.replaceState({}, "", "/?page=Home");
    window.scrollTo = () => undefined;
  });

  it("renders the wiki source with navigation and an on-page outline", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "RouteDeck Wiki" })).toBeVisible();
    expect(screen.getByRole("complementary", { name: "Documentation navigation" })).toBeVisible();
    expect(screen.getByRole("complementary", { name: "On this page" })).toBeVisible();
  });

  it("navigates between source pages without reloading", () => {
    render(<App />);

    const sidebar = screen.getByRole("complementary", { name: "Documentation navigation" });
    fireEvent.click(within(sidebar).getByRole("link", { name: "Hello World" }));

    expect(screen.getByRole("heading", { level: 1, name: "Hello World" })).toBeVisible();
    expect(window.location.search).toBe("?page=Hello-World");
  });

  it("searches across page titles and content", () => {
    render(<App />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search documentation" }), {
      target: { value: "external writes" },
    });

    expect(screen.getByRole("listbox", { name: "Documentation search results" })).toBeVisible();
    const results = screen.getByRole("listbox", { name: "Documentation search results" });
    expect(within(results).getByRole("button", { name: /operations and supervision/i })).toBeVisible();
  });

  it("preserves Mermaid diagrams as explicit source until a renderer is approved", () => {
    window.history.replaceState({}, "", "/?page=Architecture");
    render(<App />);

    const diagrams = screen.getAllByTestId("diagram-source");
    expect(diagrams.length).toBeGreaterThan(0);
    expect(diagrams.every((diagram) => diagram.textContent?.includes("Mermaid source"))).toBe(true);
    expect(diagrams.some((diagram) => diagram.textContent?.includes("flowchart TB"))).toBe(true);
  });
});
