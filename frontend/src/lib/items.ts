import { useQuery } from "@tanstack/react-query";

import { api } from "./api";

export type ItemStatus = "pending" | "fetching" | "done" | "failed";

export type ItemSummary = {
  id: string;
  url: string;
  url_submitted: string;
  status: ItemStatus;
  error: string;
  title: string;
  description: string;
  created_at: string;
  fetched_at: string | null;
};

export type Item = ItemSummary & {
  markdown: string;
};

export const itemsKey = ["items"];

export function useItems() {
  return useQuery({
    queryKey: itemsKey,
    queryFn: () => api<ItemSummary[]>("/items"),
  });
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
