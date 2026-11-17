import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";

import { api } from "../lib/api";
import { type User, sessionKey, useSession } from "../lib/auth";

export function Login() {
  const { data: user } = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { created, from } = useLocation().state ?? {};
  // Where RequireAuth sent us from, e.g. the bookmarklet's /save popup.
  const next = from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () =>
      api<User>("/auth/login", { method: "POST", body: { email, password } }),
    onSuccess: (user) => {
      queryClient.setQueryData(sessionKey, user);
      navigate(next, { replace: true });
    },
  });

  if (user) return <Navigate to={next} replace />;

  function submit(e: FormEvent) {
    e.preventDefault();
    login.mutate();
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>Log in</h1>
      {created && <p className="notice">Account created. Log in.</p>}
      {login.error && <p className="error">{login.error.message}</p>}
      <label>
        Email
        <input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <button type="submit" disabled={login.isPending}>
        Log in
      </button>
      <p>
        No account? <Link to="/signup">Sign up</Link>
      </p>
    </form>
  );
}
