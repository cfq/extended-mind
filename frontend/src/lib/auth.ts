import { useQuery } from "@tanstack/react-query";

import { ApiError, api } from "./api";

export type User = {
  username: string;
  email: string;
};

export const sessionKey = ["session"];

// null = not logged in.
export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: () =>
      api<User>("/auth/session").catch((e) => {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }),
    retry: false,
  });
}
