import { Link } from "react-router";

import { displayTitle, useItems } from "../lib/items";

export function Dashboard() {
  const { data: items, error } = useItems();

  if (error) return <p className="error">{error.message}</p>;
  if (!items) return null;
  if (items.length === 0) {
    return (
      <p>
        Nothing saved yet. <Link to="/add">Add something</Link>.
      </p>
    );
  }

  return (
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
        </li>
      ))}
    </ul>
  );
}
