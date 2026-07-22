export type DocPage = {
  slug: string;
  title: string;
  source: string;
  description: string;
};

export type NavGroup = {
  label: string;
  pages: readonly string[];
};

const sources = import.meta.glob<string>("../../wiki/*.md", {
  eager: true,
  import: "default",
  query: "?raw",
});

export const navigation: readonly NavGroup[] = [
  {
    label: "Start",
    pages: ["Home", "Hello-World", "Core-Concepts", "Architecture", "How-RouteDeck-Works"],
  },
  {
    label: "Build",
    pages: [
      "Applications-and-the-Navgraph",
      "Operations-and-Supervision",
      "Sessions-Persistence-and-Events",
      "Projection-Surfaces-and-Privacy",
      "Navigation-and-History",
      "Conversation-and-LangGraph",
      "HTTP-Browser-and-React",
    ],
  },
  {
    label: "Operate",
    pages: ["Failure-Semantics", "Testing-and-Diagnostics", "Medusa-Reference-Application"],
  },
  {
    label: "Look up",
    pages: ["Glossary", "FAQ"],
  },
] as const;

const pageOrder = navigation.flatMap((group) => group.pages);

function titleFromSource(source: string, slug: string): string {
  return source.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? slug.replaceAll("-", " ");
}

function descriptionFromSource(source: string): string {
  const withoutTitle = source.replace(/^#\s+.+$/m, "").trim();
  const paragraph = withoutTitle
    .split(/\n\s*\n/)
    .find((section) => !section.startsWith("```") && !section.startsWith(">"));
  return paragraph?.replace(/\s+/g, " ").slice(0, 180) ?? "RouteDeck documentation";
}

function sourceForSlug(slug: string): string {
  const entry = Object.entries(sources).find(([path]) => path.endsWith(`/${slug}.md`));
  if (entry === undefined) {
    throw new Error(`Missing wiki source for ${slug}`);
  }
  return entry[1];
}

export const pages: readonly DocPage[] = pageOrder.map((slug) => {
  const source = sourceForSlug(slug);
  return {
    slug,
    title: titleFromSource(source, slug),
    source,
    description: descriptionFromSource(source),
  };
});

export const pagesBySlug = new Map(pages.map((page) => [page.slug, page]));

export function pageForSlug(slug: string | null): DocPage {
  return pagesBySlug.get(slug ?? "") ?? pagesBySlug.get("Home")!;
}

export function adjacentPages(slug: string): {
  previous: DocPage | null;
  next: DocPage | null;
} {
  const index = pages.findIndex((page) => page.slug === slug);
  return {
    previous: index > 0 ? pages[index - 1] : null,
    next: index >= 0 && index < pages.length - 1 ? pages[index + 1] : null,
  };
}
