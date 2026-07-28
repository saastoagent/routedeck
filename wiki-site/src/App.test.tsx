import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const mermaidMocks = vi.hoisted(() => ({
  initialize: vi.fn(),
  render: vi.fn(async (id: string, source: string) => ({
    svg: `<svg id="${id}" data-source="${source.split("\n", 1)[0]}"></svg>`,
  })),
}));

vi.mock("mermaid", () => ({
  default: mermaidMocks,
}));

describe("RouteDeck wiki site", () => {
  afterEach(cleanup);

  beforeEach(() => {
    mermaidMocks.render.mockClear();
    mermaidMocks.render.mockImplementation(async (id: string, source: string) => ({
      svg: `<svg id="${id}" data-source="${source.split("\n", 1)[0]}"></svg>`,
    }));
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

  it("renders Mermaid source as a secured SVG diagram", async () => {
    window.history.replaceState({}, "", "/?page=Architecture");
    render(<App />);

    const diagrams = await screen.findAllByTestId("diagram-rendered");
    expect(diagrams).toHaveLength(1);
    expect(diagrams[0].querySelector("svg")).not.toBeNull();
    expect(mermaidMocks.render).toHaveBeenCalledWith(
      expect.stringMatching(/^routedeck-diagram-/),
      expect.stringContaining("flowchart TB"),
    );
    await waitFor(() => {
      expect(mermaidMocks.initialize).toHaveBeenCalledWith(
        expect.objectContaining({ securityLevel: "strict", startOnLoad: false }),
      );
    });
  });

  it("shows a visible error and the original source when Mermaid cannot render", async () => {
    mermaidMocks.render.mockRejectedValueOnce(new Error("invalid diagram"));
    window.history.replaceState({}, "", "/?page=Architecture");
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Diagram could not be rendered");
    expect(screen.getByText("flowchart TB", { exact: false })).toBeVisible();
  });
});
