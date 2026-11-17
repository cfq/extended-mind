import { useMutation, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { useNavigate, useParams } from "react-router";

import { ApiError, api } from "../lib/api";
import { type Item, displayTitle, itemsKey, useItem } from "../lib/items";
import { articleMeta } from "../lib/meta";
import { NotFound } from "./NotFound";

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
        </p>
      </header>

      <div className="reading-column">
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
            <Markdown>{item.markdown}</Markdown>
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
