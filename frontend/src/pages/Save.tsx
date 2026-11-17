import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { api } from "../lib/api";
import { type Item, itemsKey } from "../lib/items";

const CLOSE_AFTER_MS = 800;

// Bookmarklet popup: saves ?url= straight away, then closes itself.
export function Save() {
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const url = params.get("url") ?? "";
  const started = useRef(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // StrictMode runs effects twice in dev; save once.
    if (started.current) return;
    started.current = true;
    api<Item>("/items", { method: "POST", body: { url } })
      .then(() => {
        setSaved(true);
        queryClient.invalidateQueries({ queryKey: itemsKey });
        // Only works when the bookmarklet opened this window.
        setTimeout(() => window.close(), CLOSE_AFTER_MS);
      })
      .catch((e: Error) => setError(e.message));
  }, [url, queryClient]);

  return (
    <div className="card">
      <h1>{error ? "Not saved" : saved ? "Saved" : "Saving…"}</h1>
      {error && <p className="error">{error}</p>}
      <p className="url">{url}</p>
    </div>
  );
}
