import assert from "node:assert/strict";
import test from "node:test";

import { normalizeTag, tagOptions } from "./tags.ts";

const all = [
  { name: "art", slug: "art", count: 1 },
  { name: "art nouveau", slug: "art-nouveau", count: 5 },
  { name: "smart cities", slug: "smart-cities", count: 9 },
  { name: "design", slug: "design", count: 3 },
];

const names = (options: { name: string; create: boolean }[]) =>
  options.map((o) => (o.create ? `+${o.name}` : o.name));

test("normalizeTag", () => {
  assert.equal(normalizeTag("  Open   Source "), "open source");
  assert.equal(normalizeTag("C++"), "c++");
  assert.equal(normalizeTag("---"), "");
  assert.equal(normalizeTag("x".repeat(51)), "");
});

test("tagOptions: prefix matches first, then most used", () => {
  assert.deepEqual(names(tagOptions(all, [], "art")), ["art nouveau", "art", "smart cities"]);
});

test("tagOptions: leaves out applied tags", () => {
  assert.deepEqual(names(tagOptions(all, ["art nouveau"], "art")), ["art", "smart cities"]);
});

test("tagOptions: offers to create a new tag", () => {
  assert.deepEqual(names(tagOptions(all, [], " Des")), ["design", "+des"]);
  assert.deepEqual(names(tagOptions(all, [], "zines")), ["+zines"]);
});

test("tagOptions: no create for an existing or applied tag", () => {
  assert.deepEqual(names(tagOptions(all, [], "Design")), ["design"]);
  assert.deepEqual(names(tagOptions(all, ["design"], "design")), []);
});

test("tagOptions: empty text lists most used, capped", () => {
  assert.deepEqual(names(tagOptions(all, [], "", 2)), ["smart cities", "art nouveau"]);
});
