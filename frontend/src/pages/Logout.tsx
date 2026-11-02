import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate } from "react-router";

import { api } from "../lib/api";
import { sessionKey } from "../lib/auth";

export function Logout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    api("/auth/logout", { method: "POST" }).finally(() => {
      queryClient.setQueryData(sessionKey, null);
      navigate("/login", { replace: true });
    });
  }, [queryClient, navigate]);

  return null;
}
