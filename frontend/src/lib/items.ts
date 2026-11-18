import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import { type ItemTag, type Tag, tagsKey } from "./tags";

export type ItemStatus = "pending" | "fetching" | "done" | "failed";

export type ItemSummary = {
  id: string;
  url: string;
  url_submitted: string;
  status: ItemStatus;
  error: string;
  title: string;
  description: string;
  author: string;
  site_name: string;
  published_at: string | null;
  created_at: string;
  fetched_at: string | null;
  tags: ItemTag[];
};

export type Item = ItemSummary & {
  markdown: string;
};

export const itemsKey = ["items"];

// Unfiltered list is ["items"]; a tag filter adds {tag}.
export function useItems(tag?: string) {
  return useQuery({
    queryKey: tag ? [...itemsKey, { tag }] : itemsKey,
    queryFn: () =>
      api<ItemSummary[]>(tag ? `/items?tag=${encodeURIComponent(tag)}` : "/items"),
  });
}

export function useTags() {
  return useQuery({ queryKey: tagsKey, queryFn: () => api<Tag[]>("/tags") });
}

export function useItem(id: string) {
  return useQuery({
    queryKey: [...itemsKey, id],
    queryFn: () => api<Item>(`/items/${id}`),
    retry: false,
  });
}

// Until fetched there's no title; show the URL instead.
export function displayTitle(item: ItemSummary): string {
  return item.title || item.url;
}
