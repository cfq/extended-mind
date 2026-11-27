import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type DragEvent, type FormEvent, useEffect, useRef, useState } from "react";
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
      <UploadForm />
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

const IMAGE_TYPES = "image/jpeg,image/png,image/gif,image/webp";

function UploadForm() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [foundOn, setFoundOn] = useState("");
  const [dragging, setDragging] = useState(false);

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      for (const file of files) form.append("file", file);
      if (foundOn.trim()) form.append("found_on", foundOn.trim());
      return api<Item[]>("/items/images", { method: "POST", body: form });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemsKey });
      navigate("/");
    },
  });

  function drop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = [...e.dataTransfer.files].filter((f) => f.type.startsWith("image/"));
    if (dropped.length) setFiles(dropped);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (files.length) upload.mutate();
  }

  return (
    <form
      className={`card upload${dragging ? " upload-dragging" : ""}`}
      onSubmit={submit}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={drop}
    >
      <h2>Upload images</h2>
      {upload.error && <p className="error">{upload.error.message}</p>}
      <label>
        Images (or drop them here)
        <input
          type="file"
          accept={IMAGE_TYPES}
          multiple
          onChange={(e) => setFiles([...(e.target.files ?? [])])}
        />
      </label>
      {files.length > 0 && (
        <p className="upload-files">
          {files.length === 1 ? files[0].name : `${files.length} images`}
        </p>
      )}
      <label>
        Found on (optional)
        <input
          type="url"
          placeholder="https://"
          value={foundOn}
          onChange={(e) => setFoundOn(e.target.value)}
        />
      </label>
      <button type="submit" disabled={!files.length || upload.isPending}>
        {upload.isPending ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
