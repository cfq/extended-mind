import assert from "node:assert/strict";
import test from "node:test";

import {
  isSuggestion,
  keepOrder,
  normalizeTag,
  sortTags,
  splitTyped,
  tagOptions,
  tagPath,
  typingTag,
} from "./tags.ts";

const all = [
  { name: "art", slug: "art", count: 1 },
  { name: "art-nouveau", slug: "art-nouveau", count: 5 },
  { name: "smart-cities", slug: "smart-cities", count: 9 },
  { name: "design", slug: "design", count: 3 },
];

const names = (options: { name: string; create: boolean }[]) =>
  options.map((o) => (o.create ? `+${o.name}` : o.name));

test("normalizeTag: ASCII kebab-case, like the backend", () => {
  assert.equal(normalizeTag("Artificial intelligence "), "artificial-intelligence");
  assert.equal(normalizeTag("  Open   Source "), "open-source");
  assert.equal(normalizeTag("art—nouveau"), "art-nouveau");
  assert.equal(normalizeTag("Apple’s word"), "apples-word");
  assert.equal(normalizeTag("sagrada família"), "sagrada-familia");
  assert.equal(normalizeTag("café crème"), "cafe-creme");
  assert.equal(normalizeTag("日本"), "");
  assert.equal(normalizeTag("#Design"), "design");
  assert.equal(normalizeTag("C++"), "c++");
  assert.equal(normalizeTag("c#"), "c#");
  assert.equal(normalizeTag("a_b"), "a-b");
  assert.equal(normalizeTag("---"), "");
  assert.equal(normalizeTag("x".repeat(51)), "");
});

test("typingTag keeps a trailing hyphen while typing", () => {
  assert.equal(typingTag("Artificial "), "artificial-");
  assert.equal(typingTag(" Art  Nouveau"), "art-nouveau");
  assert.equal(typingTag("long--dash"), "long-dash");
});

test("splitTyped: commas finish tags", () => {
  assert.deepEqual(splitTyped("Art, Graphic design ,ph"), {
    done: ["art", "graphic-design"],
    rest: "ph",
  });
  assert.deepEqual(splitTyped("art,"), { done: ["art"], rest: "" });
  assert.deepEqual(splitTyped(",,"), { done: [], rest: "" });
  assert.deepEqual(splitTyped("Machine "), { done: [], rest: "machine-" });
});

test("tagOptions: prefix matches first, then most used", () => {
  assert.deepEqual(names(tagOptions(all, [], "art")), ["art-nouveau", "art", "smart-cities"]);
});

test("tagOptions: leaves out applied tags", () => {
  assert.deepEqual(names(tagOptions(all, ["art-nouveau"], "art")), ["art", "smart-cities"]);
});

test("tagOptions: matches what a phone types", () => {
  assert.deepEqual(names(tagOptions(all, [], "Art nou")), ["art-nouveau", "+art-nou"]);
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
  assert.deepEqual(names(tagOptions(all, [], "", 2)), ["smart-cities", "art-nouveau"]);
});

test("sortTags: yours first, then suggestions, by name", () => {
  const tag = (name: string, source: "manual" | "page" | "model") => ({ name, slug: name, source });
  const sorted = sortTags([tag("zines", "model"), tag("design", "manual"), tag("art", "page"), tag("ai", "manual")]);
  assert.deepEqual(
    sorted.map((t) => t.name),
    ["ai", "design", "art", "zines"],
  );
});

test("isSuggestion: page and model tags", () => {
  assert.equal(isSuggestion({ name: "a", slug: "a", source: "manual" }), false);
  assert.equal(isSuggestion({ name: "a", slug: "a", source: "page" }), true);
  assert.equal(isSuggestion({ name: "a", slug: "a", source: "model" }), true);
});

test("tagPath", () => {
  assert.equal(tagPath("c++"), "/tag/c%2B%2B");
});

test("keepOrder: first time as given, then new ones on the end", () => {
  assert.deepEqual(keepOrder(null, ["b", "a"]), ["b", "a"]);
  assert.deepEqual(keepOrder(["b", "a"], ["a", "b", "c"]), ["b", "a", "c"]);
  assert.deepEqual(keepOrder(["b", "a", "c"], ["a", "c"]), ["a", "c"]);
});
