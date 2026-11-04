import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

import { api } from "../lib/api";
import { type Item, itemsKey } from "../lib/items";

export function Add() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [url, setUrl] = useState("");

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
  );
}
