import assert from "node:assert/strict";
import test from "node:test";

import { articleMeta, domain, formatDate, readingTime, wordCount } from "./meta.ts";

const item = {
  url: "https://www.example.com/post",
  site_name: "Example Blog",
  published_at: "2026-11-03",
  created_at: "2026-11-17T22:35:44Z",
};

test("domain strips www", () => {
  assert.equal(domain("https://www.example.com/a?b=1"), "example.com");
  assert.equal(domain("https://blog.example.com/"), "blog.example.com");
});

test("domain falls back to the input", () => {
  assert.equal(domain("not a url"), "not a url");
});

test("formatDate: date and datetime", () => {
  assert.equal(formatDate("2026-11-03"), "3 November 2026");
  assert.equal(formatDate("2026-11-17T23:59:00Z"), "17 November 2026");
});

test("articleMeta: site, published, saved", () => {
  assert.deepEqual(articleMeta(item), [
    "Example Blog",
    "3 November 2026",
    "Saved 17 November 2026",
  ]);
});

test("wordCount ignores markup and link targets", () => {
  assert.equal(wordCount("# Title\n\nSome *bold* words, [a link](https://x.com/a b)."), 6);
  assert.equal(wordCount("![](https://x.com/i.png)\n\n---\n\n- one\n- two"), 2);
  assert.equal(wordCount(""), 0);
});

test("readingTime rounds up at 238 wpm", () => {
  assert.equal(readingTime("word"), "1 min read");
  assert.equal(readingTime("word ".repeat(238)), "1 min read");
  assert.equal(readingTime("word ".repeat(239)), "2 min read");
  assert.equal(readingTime("  \n"), "");
});

test("articleMeta: reading time after the date", () => {
  assert.deepEqual(articleMeta({ ...item, markdown: "word ".repeat(500) }), [
    "Example Blog",
    "3 November 2026",
    "3 min read",
    "Saved 17 November 2026",
  ]);
});

test("articleMeta: falls back to domain, leaves out missing date", () => {
  assert.deepEqual(articleMeta({ ...item, site_name: "", published_at: null }), [
    "example.com",
    "Saved 17 November 2026",
  ]);
});
