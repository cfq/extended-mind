import { Link, useSearchParams } from "react-router";

import { displayTitle, useItems, useTags } from "../lib/items";
import { sourceLabel } from "../lib/tags";

export function Dashboard() {
  const [params] = useSearchParams();
  const tag = params.get("tag") ?? undefined;
  const { data: items, error } = useItems(tag);
  const { data: allTags } = useTags();

  if (error) return <p className="error">{error.message}</p>;
  if (!items) return null;
  if (items.length === 0 && !tag) {
    return (
      <p>
        Nothing saved yet. <Link to="/add">Add something</Link>.
      </p>
    );
  }

  const tagName = allTags?.find((t) => t.slug === tag)?.name ?? tag;

  return (
    <>
      {tag && (
        <p className="tag-filter">
          Tagged <strong>{tagName}</strong> · <Link to="/">Show all</Link>
        </p>
      )}
      {items.length === 0 && <p>Nothing tagged {tagName}.</p>}
      <ul className="items">
        {items.map((item) => (
          <li key={item.id}>
            <Link to={`/item/${item.id}`} className="item-title">
              {displayTitle(item)}
            </Link>
            {item.status !== "done" && (
              <span className={`status status-${item.status}`}>{item.status}</span>
            )}
            {item.description && <p className="item-description">{item.description}</p>}
            {item.tags.length > 0 && (
              <ul className="tag-list item-tags">
                {item.tags.map((t) => (
                  <li key={t.slug}>
                    <Link
                      to={`/?tag=${encodeURIComponent(t.slug)}`}
                      className={`tag tag-${t.source}`}
                      title={sourceLabel(t.source)}
                    >
                      {t.name}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
