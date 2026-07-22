import { useEffect, useMemo, useRef, useState } from "react";

import {
  adjacentPages,
  navigation,
  pageForSlug,
  pages,
  pagesBySlug,
  type DocPage,
} from "./content";
import {
  ArrowIcon,
  ChevronIcon,
  CloseIcon,
  GitHubIcon,
  MenuIcon,
  SearchIcon,
} from "./icons";
import { headingsForSource, MarkdownArticle } from "./MarkdownArticle";

function slugFromLocation(): string | null {
  return new URL(window.location.href).searchParams.get("page");
}

function SearchResults({
  query,
  onNavigate,
}: {
  query: string;
  onNavigate: (slug: string) => void;
}) {
  const normalized = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (normalized.length < 2) {
      return [];
    }
    return pages
      .filter((page) => `${page.title}\n${page.source}`.toLowerCase().includes(normalized))
      .slice(0, 7);
  }, [normalized]);

  if (normalized.length < 2) {
    return null;
  }

  return (
    <div className="search-results" role="listbox" aria-label="Documentation search results">
      {results.length === 0 ? (
        <p>No documentation matched “{query}”.</p>
      ) : (
        results.map((page) => (
          <button key={page.slug} type="button" onClick={() => onNavigate(page.slug)}>
            <strong>{page.title}</strong>
            <span>{page.description}</span>
          </button>
        ))
      )}
    </div>
  );
}

function Sidebar({
  page,
  open,
  onClose,
  onNavigate,
}: {
  page: DocPage;
  open: boolean;
  onClose: () => void;
  onNavigate: (slug: string) => void;
}) {
  return (
    <>
      <button
        className={open ? "sidebar-scrim visible" : "sidebar-scrim"}
        type="button"
        aria-label="Close documentation navigation"
        onClick={onClose}
      />
      <aside className={open ? "sidebar open" : "sidebar"} aria-label="Documentation navigation">
        <div className="sidebar-mobile-heading">
          <span>Documentation</span>
          <button type="button" aria-label="Close menu" onClick={onClose}><CloseIcon /></button>
        </div>
        <nav>
          {navigation.map((group) => (
            <section key={group.label} className="nav-group">
              <h2>{group.label}</h2>
              <ul>
                {group.pages.map((slug) => {
                  const item = pagesBySlug.get(slug)!;
                  return (
                    <li key={slug}>
                      <a
                        className={page.slug === slug ? "active" : undefined}
                        href={`/?page=${encodeURIComponent(slug)}`}
                        aria-current={page.slug === slug ? "page" : undefined}
                        onClick={(event) => {
                          event.preventDefault();
                          onNavigate(slug);
                        }}
                      >
                        {item.title === "RouteDeck Wiki" ? "Overview" : item.title}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" />
          <span>Alpha documentation</span>
        </div>
      </aside>
    </>
  );
}

function PageFooter({
  previous,
  next,
  onNavigate,
}: {
  previous: DocPage | null;
  next: DocPage | null;
  onNavigate: (slug: string) => void;
}) {
  return (
    <nav className="page-footer" aria-label="Adjacent documentation pages">
      {previous === null ? <span /> : (
        <button type="button" className="previous" onClick={() => onNavigate(previous.slug)}>
          <ChevronIcon />
          <span><small>Previous</small><strong>{previous.title}</strong></span>
        </button>
      )}
      {next === null ? <span /> : (
        <button type="button" className="next" onClick={() => onNavigate(next.slug)}>
          <span><small>Next</small><strong>{next.title}</strong></span>
          <ArrowIcon />
        </button>
      )}
    </nav>
  );
}

export function App() {
  const [page, setPage] = useState(() => pageForSlug(slugFromLocation()));
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const headings = useMemo(() => headingsForSource(page.source), [page.source]);
  const adjacent = useMemo(() => adjacentPages(page.slug), [page.slug]);

  useEffect(() => {
    const onPopState = () => setPage(pageForSlug(slugFromLocation()));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, []);

  useEffect(() => {
    document.title = `${page.title} · RouteDeck`;
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);

  const navigate = (slug: string) => {
    const nextPage = pageForSlug(slug);
    const url = new URL(window.location.href);
    url.searchParams.set("page", nextPage.slug);
    window.history.pushState({}, "", url);
    setPage(nextPage);
    setMenuOpen(false);
    setQuery("");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="menu-button" type="button" aria-label="Open documentation menu" onClick={() => setMenuOpen(true)}>
          <MenuIcon />
        </button>
        <a className="brand" href="/?page=Home" onClick={(event) => { event.preventDefault(); navigate("Home"); }}>
          <span className="brand-mark">R</span>
          <span>RouteDeck</span>
        </a>
        <div className="search-wrap">
          <SearchIcon />
          <input
            ref={searchRef}
            type="search"
            placeholder="Search documentation"
            aria-label="Search documentation"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <kbd>Ctrl K</kbd>
          <SearchResults query={query} onNavigate={navigate} />
        </div>
        <a className="github-link" href="https://github.com/saastoagent/routedeck" target="_blank" rel="noreferrer">
          <GitHubIcon />
          <span>GitHub</span>
        </a>
      </header>

      <Sidebar page={page} open={menuOpen} onClose={() => setMenuOpen(false)} onNavigate={navigate} />

      <main className="content-grid">
        <div className="article-column">
          <MarkdownArticle page={page} onNavigate={navigate} />
          <PageFooter previous={adjacent.previous} next={adjacent.next} onNavigate={navigate} />
        </div>
        <aside className="page-outline" aria-label="On this page">
          <h2>On this page</h2>
          <nav>
            {headings.length === 0 ? <span>No sections</span> : headings.map((heading) => (
              <a key={`${heading.id}-${heading.level}`} className={heading.level === 3 ? "nested" : undefined} href={`#${heading.id}`}>
                {heading.label}
              </a>
            ))}
          </nav>
        </aside>
      </main>
    </div>
  );
}
