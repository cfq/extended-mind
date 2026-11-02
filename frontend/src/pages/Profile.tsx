import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { ApiError, api } from "../lib/api";
import type { User } from "../lib/auth";
import { NotFound } from "./NotFound";

export function Profile() {
  const { username } = useParams();
  const { data: user, error } = useQuery({
    queryKey: ["user", username],
    queryFn: () => api<User>(`/users/${username}`),
    retry: false,
  });

  if (error instanceof ApiError && error.status === 404) return <NotFound />;
  if (error) return <p className="error">{error.message}</p>;
  if (!user) return null;

  return (
    <dl className="card">
      <dt>Username</dt>
      <dd>{user.username}</dd>
      <dt>Email</dt>
      <dd>{user.email}</dd>
    </dl>
  );
}
