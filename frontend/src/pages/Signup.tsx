import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { api } from "../lib/api";
import type { User } from "../lib/auth";

export function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const signup = useMutation({
    mutationFn: () =>
      api<User>("/auth/signup", {
        method: "POST",
        body: { email, username, password },
      }),
    onSuccess: () => navigate("/login", { state: { created: true } }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    signup.mutate();
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>Sign up</h1>
      {signup.error && <p className="error">{signup.error.message}</p>}
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
        Username
        <input
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <p className="hint">
        At least 8 characters, not entirely numbers, not a common password,
        and not too similar to your email or username.
      </p>
      <button type="submit" disabled={signup.isPending}>
        Sign up
      </button>
      <p>
        Have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  );
}
