import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import Markdown, { type Components } from "react-markdown";
import { useNavigate, useParams } from "react-router";

import { TagInput } from "../components/TagInput";
import { ApiError, api } from "../lib/api";
import { type Item, displayTitle, itemsKey, useItem, useTags } from "../lib/items";
import { articleMeta } from "../lib/meta";
import { type ItemTag, tagsKey } from "../lib/tags";
import { NotFound } from "./NotFound";

// In-page anchors from extraction ([](#anchor:id)) and links to them
// (#id), prefixed so they can't clash with the app's own ids.
const anchorId = (id: string) => `note-${decodeURIComponent(id)}`;

const markdownComponents: Components = {
  img: ({ node: _, ...props }) => <img loading="lazy" {...props} />,
  a: ({ node: _, href = "", children, ...props }) => {
    if (href.startsWith("#anchor:")) return <span id={anchorId(href.slice(8))} />;
    if (href.startsWith("#")) {
      return (
        <a href={`#${anchorId(href.slice(1))}`} {...props}>
          {children}
        </a>
      );
    }
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
};

export function ItemPage() {
  const { id = "" } = useParams();
  const { data: item, error } = useItem(id);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const retry = useMutation({
    mutationFn: () => api<Item>(`/items/${id}/retry`, { method: "POST" }),
    onSuccess: (updated) => {
      queryClient.setQueryData([...itemsKey, id], updated);
      queryClient.invalidateQueries({ queryKey: itemsKey, exact: true });
    },
  });

  const { data: allTags = [] } = useTags();

  // Both return the item's tags after the change.
  type TagChange = { add?: string; remove?: string };
  const tagsMutationKey = ["item-tags", id];
  const changeTags = useMutation({
    mutationKey: tagsMutationKey,
    mutationFn: ({ add, remove }: TagChange) =>
      add
        ? api<ItemTag[]>(`/items/${id}/tags`, { method: "POST", body: { name: add } })
        : api<ItemTag[]>(`/items/${id}/tags/${encodeURIComponent(remove ?? "")}`, {
            method: "DELETE",
          }),
    onSuccess: (tags) => {
      queryClient.setQueryData<Item>([...itemsKey, id], (old) => old && { ...old, tags });
      queryClient.invalidateQueries({ queryKey: tagsKey });
      // Also refetches this item: two quick adds can finish out of order.
      queryClient.invalidateQueries({ queryKey: itemsKey });
    },
  });

  // Adds in flight, shown greyed until confirmed.
  const pendingTags = useMutationState({
    filters: { mutationKey: tagsMutationKey, status: "pending" },
    select: (mutation) => (mutation.state.variables as TagChange).add ?? "",
  }).filter(Boolean);

  const remove = useMutation({
    mutationFn: () => api(`/items/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemsKey });
      navigate("/");
    },
  });

  if (error instanceof ApiError && error.status === 404) return <NotFound />;
  if (error) return <p className="error">{error.message}</p>;
  if (!item) return null;

  return (
    <article className="reading">
      <header className="reading-header">
        <h1 className="reading-title">{displayTitle(item)}</h1>
        {item.author && <p className="reading-author">{item.author}</p>}
        <p className="reading-meta">
          {articleMeta(item).map((part) => (
            <span key={part}>{part}</span>
          ))}
          <a href={item.url} target="_blank" rel="noreferrer">
            Original
          </a>
          {(item.screenshots.full || item.screenshots.head) && (
            <span>
              Screenshots:{" "}
              {[
                ["full", item.screenshots.full],
                ["head", item.screenshots.head],
              ]
                .filter(([, url]) => url)
                .map(([label, url], i) => (
                  <span key={label}>
                    {i > 0 && ", "}
                    <a href={url ?? ""} target="_blank" rel="noreferrer">
                      {label}
                    </a>
                  </span>
                ))}
            </span>
          )}
          {item.pdf && (
            <a href={item.pdf} target="_blank" rel="noreferrer">
              PDF
            </a>
          )}
        </p>
      </header>

      <div className="reading-column">
        <div className="reading-tags">
          <TagInput
            key={id}
            tags={item.tags}
            allTags={allTags}
            pending={pendingTags}
            onAdd={(name) => changeTags.mutate({ add: name })}
            onRemove={(slug) => changeTags.mutate({ remove: slug })}
          />
          {changeTags.error && <p className="error">{changeTags.error.message}</p>}
        </div>

        {item.status !== "done" && (
          <p className="reading-meta reading-status">
            <span>{item.status === "failed" ? item.error || "Failed" : `${item.status}…`}</span>
            {item.status === "failed" && (
              <button
                type="button"
                className="quiet"
                onClick={() => retry.mutate()}
                disabled={retry.isPending}
              >
                Retry
              </button>
            )}
          </p>
        )}

        {item.description && <p className="reading-standfirst">{item.description}</p>}

        {item.markdown && (
          <div className="reading-body">
            {/* No raw HTML rendering: never add rehype-raw. */}
            <Markdown components={markdownComponents}>{item.markdown}</Markdown>
          </div>
        )}

        <footer className="reading-meta reading-footer">
          <button
            type="button"
            className="quiet"
            disabled={remove.isPending}
            onClick={() => confirm("Delete this item?") && remove.mutate()}
          >
            Delete
          </button>
        </footer>
      </div>
    </article>
  );
}
