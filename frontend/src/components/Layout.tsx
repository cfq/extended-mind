import { Link, Outlet } from "react-router";

import { useSession } from "../lib/auth";

export function Layout() {
  const { data: user } = useSession();

  return (
    <>
      <header className="header">
        <Link to="/" className="brand" aria-label="Extended Mind">
          <span className="brand-long">Extended Mind</span>
          <span className="brand-short" aria-hidden="true">
            EM
          </span>
        </Link>
        <nav>
          <Link to="/add">Add</Link>
          {user && <Link to="/settings">{user.username}</Link>}
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </>
  );
}
