import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import { type ItemTag, type Tag, tagsKey } from "./tags";

export type ItemStatus = "pending" | "fetching" | "done" | "failed";

// "" until the fetch knows what a saved URL is.
export type ItemType = "page" | "image" | "";

export type ItemSummary = {
  id: string;
  type: ItemType;
  // The item's own address; "" for uploads.
  url: string;
  url_submitted: string;
  // Where it was seen, when that isn't url.
  found_on: string | null;
  status: ItemStatus;
  error: string;
  title: string;
  description: string;
  site_name: string;
  published_at: string | null;
  created_at: string;
  fetched_at: string | null;
  tags: ItemTag[];
  // List image: the image, or a page's sharing image or head screenshot.
  thumbnail: string | null;
};

export type PageDetail = {
  author: string;
  markdown: string;
  meta: Record<string, string | string[]>;
  // URLs of the saved PNGs, null when there's none.
  screenshots: { full: string | null; head: string | null };
  pdf: string | null;
  og_image: string | null;
};

export type ImageDetail = {
  width: number | null;
  height: number | null;
  original: string | null;
  mime: string | null;
  size: number | null;
};

// One typed section, by type; both null until the type is known.
export type Item = ItemSummary & {
  page: PageDetail | null;
  image: ImageDetail | null;
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
  return item.title || item.url || item.url_submitted;
}
