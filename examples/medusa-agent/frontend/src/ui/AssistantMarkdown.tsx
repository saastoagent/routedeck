import ReactMarkdown, {
  defaultUrlTransform,
  type Components,
  type UrlTransform,
} from "react-markdown";
import remarkGfm from "remark-gfm";

const safeUrlTransform: UrlTransform = (url) => defaultUrlTransform(url);

const components: Components = {
  a: ({ href = "", children, node, ...props }) => {
    void node;

    if (!href) {
      return <span>{children}</span>;
    }

    const external = /^https?:\/\//i.test(href);

    return (
      <a
        {...props}
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    );
  },
};

export function AssistantMarkdown({ children }: { children: string }) {
  return (
    <div className="assistant-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={safeUrlTransform}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
