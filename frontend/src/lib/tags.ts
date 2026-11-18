export type TagSource = "manual" | "page" | "model";

export type ItemTag = { name: string; slug: string; source: TagSource };

export type Tag = { name: string; slug: string; count: number };

export const tagsKey = ["tags"];

export const MAX_TAG = 50;

// Same rules as the backend: trimmed, single spaces, lowercase.
export function normalizeTag(name: string): string {
  const tag = name.replace(/\s+/g, " ").trim().toLowerCase();
  return tag.length <= MAX_TAG && /[\p{L}\p{N}_]/u.test(tag) ? tag : "";
}

export type TagOption = { name: string; create: boolean };

// Combo box options: matching tags not already applied (prefix matches
// first, then most used), plus "create" when the text is a new tag.
// Empty text lists the most used tags.
export function tagOptions(
  all: Tag[],
  applied: string[],
  text: string,
  limit = 8,
): TagOption[] {
  const query = normalizeTag(text);
  const taken = new Set(applied);
  const matches = all
    .filter((tag) => !taken.has(tag.name) && tag.name.includes(query))
    .sort(
      (a, b) =>
        Number(b.name.startsWith(query)) - Number(a.name.startsWith(query)) ||
        b.count - a.count ||
        a.name.localeCompare(b.name),
    )
    .slice(0, limit)
    .map((tag) => ({ name: tag.name, create: false }));
  const exists = taken.has(query) || all.some((tag) => tag.name === query);
  if (query && !exists) matches.push({ name: query, create: true });
  return matches;
}

export function sourceLabel(source: TagSource): string {
  return { manual: "", page: "From the page", model: "Suggested by the model" }[source];
}
