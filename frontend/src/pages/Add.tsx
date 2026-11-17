import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { api } from "../lib/api";
import { bookmarklet } from "../lib/bookmarklet";
import { type Item, itemsKey } from "../lib/items";

export function Add() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const link = useRef<HTMLAnchorElement>(null);

  // React refuses javascript: URLs in JSX, so set the href on the element.
  useEffect(() => {
    link.current?.setAttribute("href", bookmarklet(window.location.origin));
  }, []);

  const add = useMutation({
    mutationFn: () => api<Item>("/items", { method: "POST", body: { url } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemsKey });
      navigate("/");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  return (
    <>
      <form className="card" onSubmit={submit}>
        <h1>Add</h1>
        {add.error && <p className="error">{add.error.message}</p>}
        <label>
          URL
          <input
            type="url"
            required
            autoFocus
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </label>
        <button type="submit" disabled={add.isPending}>
          Save
        </button>
      </form>
      <section className="card">
        <h2>Bookmarklet</h2>
        <p>Drag this to your bookmarks bar. Click it on any page to save it.</p>
        <p>
          <a ref={link} className="bookmarklet" onClick={(e) => e.preventDefault()}>
            Save to Extended Mind
          </a>
        </p>
      </section>
    </>
  );
}
