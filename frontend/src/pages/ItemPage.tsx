import { useMutation, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { useNavigate, useParams } from "react-router";

import { ApiError, api } from "../lib/api";
import { type Item, displayTitle, itemsKey, useItem } from "../lib/items";
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
    <article className="item">
      <h1>{displayTitle(item)}</h1>
      <p className="item-meta">
        <a href={item.url} target="_blank" rel="noreferrer">
          {item.url}
        </a>
        {item.status !== "done" && (
          <span className={`status status-${item.status}`}>{item.status}</span>
        )}
      </p>
      {item.status === "failed" && (
        <p className="error">
          {item.error}{" "}
          <button type="button" onClick={() => retry.mutate()} disabled={retry.isPending}>
            Retry
          </button>
        </p>
      )}
      {item.description && <p className="item-description">{item.description}</p>}
      {item.markdown && (
        <div className="article">
          {/* No raw HTML rendering: never add rehype-raw. */}
          <Markdown>{item.markdown}</Markdown>
        </div>
      )}
      <p>
        <button
          type="button"
          className="danger"
          disabled={remove.isPending}
          onClick={() => confirm("Delete this item?") && remove.mutate()}
        >
          Delete
        </button>
      </p>
    </article>
  );
}
