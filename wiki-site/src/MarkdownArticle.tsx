import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { DocPage } from "./content";
import { MermaidDiagram } from "./MermaidDiagram";

type MarkdownArticleProps = {
  page: DocPage;
  onNavigate: (slug: string) => void;
};

export type HeadingLink = {
  id: string;
  label: string;
  level: 2 | 3;
};

export function slugifyHeading(value: string): string {
  return value
    .toLowerCase()
    .replace(/[`*_]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function headingsForSource(source: string): readonly HeadingLink[] {
  return [...source.matchAll(/^(##|###)\s+(.+)$/gm)].map((match) => ({
    id: slugifyHeading(match[2]),
    label: match[2].replace(/[`*_]/g, ""),
    level: match[1] === "##" ? 2 : 3,
  }));
}

function textFromChildren(children: ReactNode): string {
  if (typeof children === "string" || typeof children === "number") {
    return String(children);
  }
  if (Array.isArray(children)) {
    return children.map(textFromChildren).join("");
  }
  return "";
}

function internalSlug(href: string | undefined): string | null {
  if (href === undefined || /^(https?:|mailto:|#)/.test(href)) {
    return null;
  }
  const target = href.split("#", 1)[0].replace(/^\.\//, "").replace(/\.md$/, "");
  return target || null;
}

export function MarkdownArticle({ page, onNavigate }: MarkdownArticleProps) {
  const components: Components = {
    h1: ({ node: _node, children, ...props }) => (
      <h1 id={slugifyHeading(textFromChildren(children))} {...props}>{children}</h1>
    ),
    h2: ({ node: _node, children, ...props }) => (
      <h2 id={slugifyHeading(textFromChildren(children))} {...props}>{children}</h2>
    ),
    h3: ({ node: _node, children, ...props }) => (
      <h3 id={slugifyHeading(textFromChildren(children))} {...props}>{children}</h3>
    ),
    a: ({ node: _node, href, children, ...props }) => {
      const slug = internalSlug(href);
      if (slug === null) {
        return <a href={href} {...props}>{children}</a>;
      }
      return (
        <a
          href={`/?page=${encodeURIComponent(slug)}`}
          onClick={(event) => {
            event.preventDefault();
            onNavigate(slug);
          }}
          {...props}
        >
          {children}
        </a>
      );
    },
    code: ({ node: _node, className, children, ...props }) => {
      if (className === "language-mermaid") {
        return <MermaidDiagram source={textFromChildren(children)} />;
      }
      return <code className={className} {...props}>{children}</code>;
    },
  };

  return (
    <article className="markdown-article" data-page={page.slug}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {page.source}
      </ReactMarkdown>
    </article>
  );
}
