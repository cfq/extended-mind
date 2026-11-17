type MetaSource = {
  url: string;
  site_name: string;
  published_at: string | null;
  created_at: string;
};

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
  const parts = [item.site_name || domain(item.url)];
  if (item.published_at) parts.push(formatDate(item.published_at));
  parts.push(`Saved ${formatDate(item.created_at)}`);
  return parts;
}
