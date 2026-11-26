import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import Markdown, { type Components } from "react-markdown";
import { useNavigate, useParams } from "react-router";

import { TagInput } from "../components/TagInput";
import { ApiError, api } from "../lib/api";
import {
  type ImageDetail,
  type Item,
  displayTitle,
  itemsKey,
  useItem,
  useTags,
} from "../lib/items";
import { articleMeta, domain } from "../lib/meta";
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
  const { page, image } = item;

  return (
    <article className="reading">
      <header className="reading-header">
        <h1 className="reading-title">{displayTitle(item)}</h1>
        {page?.author && <p className="reading-author">{page.author}</p>}
        <p className="reading-meta">
          {articleMeta({ ...item, markdown: page?.markdown }).map((part) => (
            <span key={part}>{part}</span>
          ))}
          {item.url && (
            <a href={item.url} target="_blank" rel="noreferrer">
              Original
            </a>
          )}
          {item.found_on && (
            <a href={item.found_on} target="_blank" rel="noreferrer">
              Found on {domain(item.found_on)}
            </a>
          )}
          {page && (page.screenshots.full || page.screenshots.head) && (
            <span>
              Screenshots:{" "}
              {[
                ["full", page.screenshots.full],
                ["head", page.screenshots.head],
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
          {page?.pdf && (
            <a href={page.pdf} target="_blank" rel="noreferrer">
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
          </p>
        )}

        {item.description && <p className="reading-standfirst">{item.description}</p>}

        {page?.markdown && (
          <div className="reading-body">
            {/* No raw HTML rendering: never add rehype-raw. */}
            <Markdown components={markdownComponents}>{page.markdown}</Markdown>
          </div>
        )}

        {image?.original && <ImageView image={image} title={displayTitle(item)} />}

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

function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const FORMATS: Record<string, string> = {
  "image/jpeg": "JPEG",
  "image/png": "PNG",
  "image/gif": "GIF",
  "image/webp": "WebP",
};

function ImageView({ image, title }: { image: ImageDetail; title: string }) {
  const details = [
    image.width && image.height ? `${image.width} × ${image.height}` : "",
    image.mime ? (FORMATS[image.mime] ?? image.mime) : "",
    image.size ? fileSize(image.size) : "",
  ].filter(Boolean);
  return (
    <figure className="reading-image">
      <a href={image.original ?? ""} target="_blank" rel="noreferrer">
        <img src={image.original ?? ""} alt={title} />
      </a>
      {details.length > 0 && (
        <figcaption className="reading-meta">
          {details.map((part) => (
            <span key={part}>{part}</span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
