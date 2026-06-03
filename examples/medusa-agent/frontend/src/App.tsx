import { FormEvent, useState } from "react";

import type { ProductSummary } from "./hooks/useRouteDeckProjection";
import { useRouteDeckProjection } from "./hooks/useRouteDeckProjection";
import { useSSEChat } from "./hooks/useSSEChat";

export default function App() {
  const [draft, setDraft] = useState("");
  const { messages, isStreaming, sendMessage } = useSSEChat();
  const { projection, error, dispatch } = useRouteDeckProjection();
  const setupReady = projection?.surfaces?.active?.props?.setup?.ready === true;
  const setupLabel = setupReady ? "Connected" : "Needs local demo Medusa";
  const activeSurface = projection?.surfaces?.active;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = draft.trim();
    if (!next) return;
    sendMessage(next);
    setDraft("");
  };

  return (
    <main className="app-shell">
      <section className="chat-shell" aria-label="Medusa commerce chat">
        <header className="chat-header">
          <div>
            <h1>Medusa Agent</h1>
            <p>Commerce chat for demo shopping questions.</p>
          </div>
          <span className={isStreaming ? "status status-live" : "status"} aria-live="polite">
            {isStreaming ? "Streaming" : "Ready"}
          </span>
        </header>

        <section className="setup-status" aria-label="Setup readiness">
          <span className="setup-label">Setup</span>
          <span className={setupReady ? "setup-value setup-connected" : "setup-value"}>
            {error ? "Needs local demo Medusa" : setupLabel}
          </span>
        </section>

        <CommerceSurface surface={activeSurface} dispatch={dispatch} />

        <div className="messages" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Ask about products, styles, sizing, or what to look at first.</p>
            </div>
          ) : (
            messages.map((message) => (
              <div className={`message-row ${message.role}`} key={message.id}>
                <div className="message-bubble">
                  {message.content || (message.isStreaming ? "..." : "")}
                </div>
              </div>
            ))
          )}
        </div>

        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <input
            id="message"
            aria-label="Message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask for shopping help"
            disabled={isStreaming}
          />
          <button type="submit" disabled={isStreaming || !draft.trim()}>
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

function CommerceSurface({
  surface,
  dispatch,
}: {
  surface: NonNullable<NonNullable<ReturnType<typeof useRouteDeckProjection>["projection"]>["surfaces"]>["active"] | undefined;
  dispatch: (operationId: string, args?: Record<string, unknown>) => Promise<void>;
}) {
  if (!surface || surface.variant === "setup_status") return null;
  const props = surface.props ?? {};

  if (surface.variant === "product_list") {
    const products = props.products ?? [];
    if (!products.length) return null;
    return (
      <section className="commerce-panel" aria-label="Products">
        <div className="product-grid">
          {products.map((product) => (
            <ProductCard
              key={product.product_ref}
              product={product}
              onView={() => dispatch("catalog.open", { product_ref: product.product_ref })}
            />
          ))}
        </div>
      </section>
    );
  }

  if (surface.variant === "product_detail" && props.product) {
    const product = props.product;
    const selected = props.selected_variant_ref;
    return (
      <section className="commerce-panel" aria-label="Product details">
        <div className="product-detail">
          <ProductMedia product={product} />
          <div className="product-copy">
            <h2>{product.title}</h2>
            {product.description ? <p>{product.description}</p> : null}
            <div className="variant-row" aria-label="Variants">
              {(product.variants ?? []).map((variant) => (
                <button
                  className={selected === variant.variant_ref ? "variant-button selected" : "variant-button"}
                  key={variant.variant_ref}
                  onClick={() => dispatch("variant.select", { variant_ref: variant.variant_ref })}
                  type="button"
                >
                  {variant.title}
                </button>
              ))}
            </div>
            <button
              className="commerce-action"
              disabled={!selected}
              onClick={() => selected && dispatch("cart.add_item", { variant_ref: selected, quantity: 1 })}
              type="button"
            >
              Add selected item
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (surface.variant === "cart_summary") {
    const items = props.cart?.items ?? [];
    return (
      <section className="commerce-panel" aria-label="Cart summary">
        <div className="cart-summary">
          <h2>Cart</h2>
          {items.length ? (
            <ul>
              {items.map((item) => (
                <li key={item.line_ref ?? `${item.title}-${item.quantity}`}>
                  <span>{item.title || "Selected item"}</span>
                  <strong>{item.quantity}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No items selected yet.</p>
          )}
        </div>
      </section>
    );
  }

  return null;
}

function ProductCard({ product, onView }: { product: ProductSummary; onView: () => void }) {
  return (
    <article className="product-card">
      <ProductMedia product={product} />
      <div className="product-card-body">
        <h2>{product.title}</h2>
        {product.description ? <p>{product.description}</p> : null}
        {product.variants?.length ? (
          <div className="variant-preview">
            {product.variants.slice(0, 3).map((variant) => (
              <span key={variant.variant_ref}>{variant.title}</span>
            ))}
          </div>
        ) : null}
        <button aria-label={`View ${product.title}`} onClick={onView} type="button">
          View
        </button>
      </div>
    </article>
  );
}

function ProductMedia({ product }: { product: ProductSummary }) {
  return product.thumbnail ? (
    <img alt="" className="product-media" src={product.thumbnail} />
  ) : (
    <div className="product-media product-media-empty" aria-hidden="true" />
  );
}
