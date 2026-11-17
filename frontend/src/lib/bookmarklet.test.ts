import assert from "node:assert/strict";
import test from "node:test";

import { bookmarklet } from "./bookmarklet.ts";

const ORIGIN = "https://em.example.com";

// Runs the bookmarklet as a browser would, on a page at `href`.
function click(href: string): unknown[][] {
  const code = bookmarklet(ORIGIN).slice("javascript:".length);
  const calls: unknown[][] = [];
  const window = { open: (...args: unknown[]) => calls.push(args) };
  new Function("window", "location", code)(window, { href });
  return calls;
}

test("is a javascript: URL with no spaces", () => {
  const link = bookmarklet(ORIGIN);

  assert.ok(link.startsWith("javascript:"));
  assert.doesNotMatch(link, /\s/);
});

test("opens /save on our origin in a popup", () => {
  const [[url, name, features]] = click("https://example.com/post");

  assert.ok(String(url).startsWith(`${ORIGIN}/save?url=`));
  assert.equal(name, "extended-mind");
  assert.match(String(features), /width=\d+,height=\d+/);
});

for (const href of [
  "https://example.com/post",
  "https://example.com/post?a=1&b=2#section",
  "https://example.com/a path/ünï?q=x%20y&url=https://other.test/?z=1",
]) {
  test(`passes the page URL intact: ${href}`, () => {
    const [[url]] = click(href);

    assert.equal(new URL(String(url)).searchParams.get("url"), href);
  });
}

test("opens exactly one popup", () => {
  assert.equal(click("https://example.com").length, 1);
});
