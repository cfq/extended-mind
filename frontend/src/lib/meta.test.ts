import assert from "node:assert/strict";
import test from "node:test";

import { articleMeta, domain, formatDate } from "./meta.ts";

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

test("articleMeta: falls back to domain, leaves out missing date", () => {
  assert.deepEqual(articleMeta({ ...item, site_name: "", published_at: null }), [
    "example.com",
    "Saved 17 November 2026",
  ]);
});
