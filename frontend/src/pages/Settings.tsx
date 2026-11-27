import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { Activity } from "../components/Activity";
import { api } from "../lib/api";
import { useSession } from "../lib/auth";

type Token = {
  id: number;
  name: string;
  hint: string;
  created_at: string;
  last_used_at: string | null;
};

type CreatedToken = Token & { key: string };

const tokensKey = ["tokens"];

function date(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Never";
}

export function Settings() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data: user } = useSession();
  const [name, setName] = useState("");
  // Shown once, straight after creating; the server keeps only a hash.
  const [created, setCreated] = useState<CreatedToken | null>(null);

  const tokens = useQuery({
    queryKey: tokensKey,
    queryFn: () => api<Token[]>("/tokens"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<CreatedToken>("/tokens", { method: "POST", body: { name } }),
    onSuccess: (token) => {
      setCreated(token);
      setName("");
      queryClient.invalidateQueries({ queryKey: tokensKey });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => api(`/tokens/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tokensKey }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <section className="settings">
      <h1>Settings</h1>

      {user && (
        <>
          <h2>Account</h2>
          <dl className="card">
            <dt>Username</dt>
            <dd>
              <Link to={`/user/${user.username}`}>{user.username}</Link>
            </dd>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </dl>
        </>
      )}

      <h2>API tokens</h2>
      <p>
        For the iOS Shortcut and scripts. Send as{" "}
        <code>Authorization: Bearer &lt;token&gt;</code> to{" "}
        <code>POST {window.location.origin}/api/v1/items</code> with{" "}
        <code>{'{"url": "…"}'}</code>.
      </p>

      {created && (
        <div className="card">
          <h2>{created.name}</h2>
          <p>Copy this now. It won't be shown again.</p>
          <code className="key">{created.key}</code>
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(created.key)}
          >
            Copy
          </button>
        </div>
      )}

      <form className="card" onSubmit={submit}>
        {create.error && <p className="error">{create.error.message}</p>}
        <label>
          Name
          <input
            required
            maxLength={100}
            placeholder="iPhone"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <button type="submit" disabled={create.isPending}>
          Create token
        </button>
      </form>

      {tokens.error && <p className="error">{tokens.error.message}</p>}
      {tokens.data && tokens.data.length > 0 && (
        <table className="tokens">
          <thead>
            <tr>
              <th>Name</th>
              <th>Token</th>
              <th>Created</th>
              <th>Last used</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tokens.data.map((token) => (
              <tr key={token.id}>
                <td>{token.name}</td>
                <td>
                  <code>{token.hint}…</code>
                </td>
                <td>{date(token.created_at)}</td>
                <td>{date(token.last_used_at)}</td>
                <td>
                  <button
                    type="button"
                    className="danger"
                    disabled={revoke.isPending}
                    onClick={() => {
                      if (confirm(`Revoke "${token.name}"?`)) {
                        revoke.mutate(token.id);
                      }
                    }}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p>
        <button type="button" className="danger" onClick={() => navigate("/logout")}>
          Log out
        </button>
      </p>

      {/* Here for now; moves to its own place later. */}
      <h2>Activity</h2>
      <Activity />
    </section>
  );
}
