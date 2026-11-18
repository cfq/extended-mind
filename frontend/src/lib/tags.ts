export type TagSource = "manual" | "page" | "model";

export type ItemTag = { name: string; slug: string; source: TagSource };

export type Tag = { name: string; slug: string; count: number };

export const tagsKey = ["tags"];

export const MAX_TAG = 50;

// Spaces, underscores and every dash a keyboard makes (iOS smart
// punctuation turns -- into —).
const SEPARATORS = /[\s_\u2010-\u2015\u2212-]+/g;

// Accents dropped: "família" → "familia".
function asciiFold(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "");
}

// As you type: lowercase, separators become one hyphen. A trailing hyphen
// stays so "artificial " can carry on to "artificial-intelligence".
export function typingTag(raw: string): string {
  return asciiFold(raw).toLowerCase().replace(SEPARATORS, "-").replace(/^-+/, "");
}

// Same rules as the backend (tagging.normalize): ASCII kebab-case,
// a-z, 0-9, + and #. Empty if unusable.
export function normalizeTag(name: string): string {
  const tag = typingTag(name)
    .replace(/[^a-z0-9+#-]/g, "")
    .replace(/^#+/, "")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
  return tag.length <= MAX_TAG && /[a-z0-9]/.test(tag) ? tag : "";
}

// Commas finish tags. Android keyboards don't report the comma key, so
// it's read from the text: "art, design, ph" → add art and design, keep "ph".
export function splitTyped(raw: string): { done: string[]; rest: string } {
  const parts = raw.split(/[,，]/);
  const rest = parts.pop() ?? "";
  return { done: parts.map(normalizeTag).filter(Boolean), rest: typingTag(rest) };
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

// Page and model tags are suggestions until you accept them.
export function isSuggestion(tag: ItemTag): boolean {
  return tag.source !== "manual";
}

export function tagPath(slug: string): string {
  return `/tag/${encodeURIComponent(slug)}`;
}

// Yours first, then suggestions; by name within each.
export function sortTags(tags: ItemTag[]): ItemTag[] {
  return [...tags].sort(
    (a, b) =>
      Number(isSuggestion(a)) - Number(isSuggestion(b)) || a.name.localeCompare(b.name),
  );
}
