type MetaSource = {
  url: string;
  site_name: string;
  published_at: string | null;
  created_at: string;
  markdown?: string;
};

// Average silent reading speed for non-fiction (Brysbaert 2019).
const WORDS_PER_MINUTE = 238;

// Words in markdown, ignoring link targets and image URLs.
export function wordCount(markdown: string): number {
  const text = markdown.replace(/\]\([^)]*\)/g, "]");
  return text.match(/\S*[\p{L}\p{N}]\S*/gu)?.length ?? 0;
}

// "8 min read"; empty when there's no text.
export function readingTime(markdown: string): string {
  const words = wordCount(markdown);
  if (!words) return "";
  return `${Math.max(1, Math.ceil(words / WORDS_PER_MINUTE))} min read`;
}

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// "2026-11-03" or an ISO datetime → "3 November 2026". Dates are shown in UTC,
// so a date-only value doesn't slip a day.
export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

// Meta line under an article's title; missing parts are left out.
export function articleMeta(item: MetaSource): string[] {
  // Uploads have no URL.
  const source = item.site_name || domain(item.url);
  const parts = source ? [source] : [];
  if (item.published_at) parts.push(formatDate(item.published_at));
  const time = readingTime(item.markdown ?? "");
  if (time) parts.push(time);
  parts.push(`Saved ${formatDate(item.created_at)}`);
  return parts;
}
