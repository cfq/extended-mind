"""Model tags: a small local embedding model, no external service.

Two passes over an article:
- the user's existing tags that are close to the article
- keyphrases from the text, ranked by closeness to the article (KeyBERT),
  picked for variety (maximal marginal relevance)
"""

import re
from collections import Counter
from collections.abc import Callable
from functools import cache

import numpy as np

from apps.items import tagging
from apps.items.models import Item, ItemTag

# Downloaded into the image at build time (docker/Dockerfile).
MODEL = "BAAI/bge-small-en-v1.5"

MAX_TAGS = 3
# Cosine similarity to the article. bge-small puts unrelated text around
# 0.4–0.5, so the bar sits well above that.
TAG_THRESHOLD = 0.6
PHRASE_THRESHOLD = 0.6
# Keyphrase variety: 0 = only relevance, 1 = only difference.
DIVERSITY = 0.5
MAX_CANDIDATES = 100
DOC_CHARS = 2000

Embed = Callable[[list[str]], np.ndarray]

STOPWORDS = set(
    """
    a about above after again against all also am an and any are aren't as at be
    because been before being below between both but by can can't cannot could
    couldn't did didn't do does doesn't doing don't down during each even ever few
    for from further get gets got had hadn't has hasn't have haven't having he her
    here hers herself him himself his how however i if in into is isn't it it's its
    itself just let like made make makes many may me might more most much must my
    myself new no nor not now of off often on once one only or other our ours
    ourselves out over own per really said same say says see seem she should so
    some still such than that that's the their theirs them themselves then there
    these they thing things this those though through to too two under until up
    upon us use used using very want was wasn't way we well were weren't what when
    where which while who whom why will with without won't would wouldn't yet you
    your yours yourself yourselves
    """.split()
)


@cache
def model_embed() -> Embed:
    from fastembed import TextEmbedding

    model = TextEmbedding(MODEL)
    return lambda texts: np.array(list(model.embed(texts)))


def document(item: Item) -> str:
    return "\n".join(
        part for part in (item.title, item.description, item.text[:DOC_CHARS]) if part
    )


WORD = re.compile(r"[^\W\d_][\w+#'’-]*[\w+#]|[^\W\d_]")


def candidates(text: str) -> list[str]:
    """Most frequent single words and repeated word pairs, no stopwords."""
    words = [re.sub(r"['’]s$", "", w) for w in WORD.findall(text.lower())]
    ok = [len(w) >= 3 and w not in STOPWORDS for w in words]
    singles, pairs = Counter(), Counter()
    for i, word in enumerate(words):
        if not ok[i]:
            continue
        singles[word] += 1
        if i + 1 < len(words) and ok[i + 1]:
            pairs[f"{word} {words[i + 1]}"] += 1
    # A pair seen once is usually chance ("novel donde"), not a phrase.
    counts = singles + Counter({p: n for p, n in pairs.items() if n >= 2})
    return [phrase for phrase, _ in counts.most_common(MAX_CANDIDATES)]


def shares_word(phrase: str, chosen: list[str]) -> bool:
    words = set(phrase.split())
    return any(words & set(other.split()) for other in chosen)


def unit(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def mmr(doc: np.ndarray, phrases: np.ndarray, count: int, threshold: float):
    """Indexes of phrases close to the doc and different from each other."""
    relevance = phrases @ doc
    chosen: list[int] = []
    left = [i for i in np.argsort(-relevance) if relevance[i] >= threshold]
    while left and len(chosen) < count:
        if chosen:
            overlap = (phrases[left] @ phrases[chosen].T).max(axis=1)
        else:
            overlap = np.zeros(len(left))
        scores = (1 - DIVERSITY) * relevance[left] - DIVERSITY * overlap
        chosen.append(left.pop(int(np.argmax(scores))))
    return chosen


def suggest(item: Item, embed: Embed | None = None) -> list[str]:
    text = document(item)
    if not text.strip():
        return []
    embed = embed or model_embed()
    doc = unit(embed([text]))[0]
    names: list[str] = []
    # Already on the item, or removed from it: don't spend a slot on them.
    taken = set(item.item_tags.values_list("tag__name", flat=True))
    taken |= set(item.tag_removals.values_list("name", flat=True))

    existing = [
        n for n in item.user.tags.values_list("name", flat=True) if n not in taken
    ]
    if existing:
        scores = unit(embed(existing)) @ doc
        ranked = sorted(zip(scores, existing, strict=True), reverse=True)
        names += [name for score, name in ranked if score >= TAG_THRESHOLD]
        names = names[:MAX_TAGS]

    phrases = [p for p in candidates(text) if p not in names and p not in taken]
    if phrases and len(names) < MAX_TAGS:
        vectors = unit(embed(phrases))
        # Extra picks, then drop overlaps ("emfcamp", "recent emfcamp").
        for i in mmr(doc, vectors, MAX_TAGS * 3, PHRASE_THRESHOLD):
            if len(names) < MAX_TAGS and not shares_word(phrases[i], names):
                names.append(phrases[i])
    return names


def autotag(item: Item, embed: Embed | None = None) -> list[ItemTag]:
    return tagging.add_tags(item, suggest(item, embed), ItemTag.Source.MODEL)
