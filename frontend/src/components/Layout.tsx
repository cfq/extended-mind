import { Link, Outlet, useNavigate } from "react-router";

import { useSession } from "../lib/auth";

export function Layout() {
  const { data: user } = useSession();
  const navigate = useNavigate();

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          Extended Mind
        </Link>
        <nav>
          <Link to="/add">Add</Link>
          {user && <Link to={`/user/${user.username}`}>{user.username}</Link>}
          <button type="button" onClick={() => navigate("/logout")}>
            Log out
          </button>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </>
  );
}
