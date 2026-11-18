# 0009 - Tagging

## Asked
- Tags on items, with the usual interface: combo box that searches and adds, tag chips with × to remove.
- Automatic tagging with a small ready-made Hugging Face model, run locally. No LLM, no external service.
- Also keep the tags the page itself declares. Auto tags are applied straight away: easier to remove than add.

## Extrapolated
- Every item-tag link records where it came from: you, the page, or the model. Auto tags look slightly different until you touch them.
- Removing an auto tag is final for that item: a retry or re-extract doesn't bring it back.
- Tags are per user. Names are case-insensitive unique; a tag with no items stays until a tag editor exists.
- Dashboard shows tags on each item; clicking one filters the list.

## Plan
### Model
- `BAAI/bge-small-en-v1.5` sentence-embedding model (33M params, ~130 MB), run with `fastembed` (ONNX runtime, no PyTorch).
- Two passes on each article:
  - Match your existing tags: embed tag names and the article, keep tags above a similarity threshold.
  - Keyphrases (KeyBERT method): candidate 1–2 word phrases from the text, ranked by similarity to the article, diversified so they're not near-duplicates.
- Up to 3 model tags per item, only above a similarity threshold.
- Model baked into the image at build time; the worker doesn't download at run time.

### Page tags
- trafilatura's `categories` and `tags` metadata, kept on extract. Up to 5, normalised.

### Data model
- `Tag`: user, name, slug. Unique per user on the normalised name.
- `ItemTag`: item, tag, source (`manual` / `page` / `model`), created_at. Unique on item + tag.
- `ItemTagRemoval`: item, tag name. Remembers auto tags you removed, so they aren't re-added.

### Worker
- Page tags added during extract.
- New task `tag_item`, queued after a successful fetch. A model failure never fails the fetch.
- `autotag` management command to backfill existing items.

### API
- Item responses gain `tags: [{name, slug, source}]`.
- `GET /tags`: your tags with item counts, for the combo box.
- `POST /items/{id}/tags` `{name}`: adds, creating the tag if new. Source becomes `manual`.
- `DELETE /items/{id}/tags/{slug}`.
- `GET /items?tag={slug}`: filter.

### Frontend
- `TagInput` component, hand-built (no new library):
  - chips with ×; Backspace in the empty input removes the last chip
  - typing filters your tags; arrow keys, Enter to pick; "Create 'x'" when there's no match; Escape closes
  - ARIA combobox and listbox roles
- Article page: tags under the meta line.
- Dashboard: tags on each item, click to filter, a clear-filter link.

## Out of scope
- Tag editor (rename, merge, delete), folders, bulk tagging, LLM tagging, non-English models.

## Agreed
- `fastembed` added; model downloaded at image build time.
- Spec: automatic tagging (page tags + local model) in scope; LLM or cloud AI tagging stays out.

## Review round 1
- Reusing existing tags was too loose ("british online" landed on an unrelated article). Fix: a higher bar for reuse, and the tag's words must appear in the article.
- Tag names are ASCII lowercase kebab-case: `artificial-intelligence`. a-z, 0-9, `+` and `#` (`c++`, `c#`); accents folded (`família` → `familia`).
- The tag input turns what a phone keyboard types into that form.

---

## Claude Notes
- Why embeddings over a zero-shot classifier (e.g. `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`): zero-shot needs a label list, and you start with no tags, so it would need a starter taxonomy; it also runs one pass per label (slow on CPU with many tags). Embeddings give new keyphrases on day one, then increasingly reuse your own tags, and the same model can power semantic search later.
- Why not a fixed topic classifier (IPTC news, tweet-topic): coarse fixed categories ("science & technology") that won't match how you tag.
- Text fed to the model: title + description + first 2,000 characters of the text; the model reads at most 512 tokens.
- Normalising (round 1): ASCII kebab-case, max 50 characters. Spaces, underscores and Unicode dashes (iOS smart punctuation) become one hyphen; a leading `#` is dropped (hashtag habit); apostrophes vanish (`apple’s` → `apples`). Same rules in `tagging.normalize` and `lib/tags.ts`. Slug from `slugify`, suffixed on collision (`c++`/`c#` both slug to `c`).
- Migration `0004_kebab_tag_names` converts existing tags and removals, merging tags that end up with the same name. Has a frozen copy of the rules.
- Thresholds and caps start as constants in code, tuned on your saved items.
- When you add a tag by hand that an auto source had already added, the source flips to `manual`.
- `reextract` adds page tags too, honouring removals.
- Versions: fastembed 0.9.1, onnxruntime 1.32 (Python 3.14 wheels).
- Image: `FASTEMBED_CACHE_PATH=/opt/models`, download in its own layer before the code copy so code changes don't re-download; `HF_HUB_OFFLINE=1` after it, so a missing model fails instead of downloading.
- Tuned on the 7 saved articles. Changes from the first cut:
  - Similarity threshold 0.6. Unrelated phrases score 0.35–0.45, good ones 0.6–0.8.
  - Word pairs must appear at least twice; one-off pairs were chance ("novel donde").
  - Tokens are Unicode words, so "Família" isn't split; possessive 's dropped.
  - A pick that shares a word with an earlier pick is skipped ("emfcamp" / "recent emfcamp").
  - Results now, e.g.: "smart-pointers, handle collisions, per-slot"; "computer science, uni, coursework"; "microsites, persuasion, superintelligence". Some noise, by design easy to remove.
- None of the 5 fixture pages declare tags; page tags tested with a synthetic page (`keywords`, `article:tag`, `article:section`). trafilatura returns `keywords` as one comma-separated string, so it's split.
- Model tags arrive in a separate job a moment after the fetch; the page shows them on the next load.
- `.items li` became `.items > li` so tag chips inside list items don't pick up row padding and borders.
- Tag chips sized in em, so the same component fits the reading view and the dashboard. On the article page they use the reading view's hairline colour.
- Round 1, model:
  - Existing-tag reuse threshold 0.7 (keyphrases stay 0.6), and every word of the tag must appear in the article (accents folded). Stops "british-online" and "superintelligence" landing on unrelated articles.
  - Tags are embedded with hyphens as spaces, which is how the model saw them in training.
  - A keyphrase that shares a word with any of the item's tags or removals is skipped ("artificial" next to "artificial-intelligence").
  - Max 3 model tags per item in total. Before this, re-running `autotag` added 3 more each time.
- Round 1, phone input:
  - The input has `autocapitalize`, `autocorrect` and spellcheck off, and `enterkeyhint="done"`.
  - Separators turn into hyphens as you type; a trailing hyphen stays until you add the tag, so "artificial " carries on to "artificial-intelligence".
  - Commas are read from the text, because Android keyboards don't report the comma key.
  - No rewriting during IME composition (predictive text), which breaks input on Android.
- After the change, each tag add or remove refetches the item: two quick adds can finish out of order.
- Dev data, round 1: your 3 manual tags and 3 removals were kept and converted. Model tags were cleared and `autotag` re-run once; a second run added nothing.
