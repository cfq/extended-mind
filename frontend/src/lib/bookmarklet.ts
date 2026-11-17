export const SAVE_PATH = "/save";

// Opens our /save page in a popup with the current page's URL.
// The popup is on our origin, so the session cookie does the auth:
// no token in the bookmark, no CORS.
export function bookmarklet(origin: string): string {
  const target = JSON.stringify(`${origin}${SAVE_PATH}?url=`);
  return `javascript:void(window.open(${target}+encodeURIComponent(location.href),"extended-mind","width=420,height=260"))`;
}
