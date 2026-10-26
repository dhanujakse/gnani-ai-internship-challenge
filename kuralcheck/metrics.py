"""Scoring: dataset-level CER (primary) and WER, variant-aware references,
number accuracy and bootstrap 95% confidence intervals.

Accepted variants (sentences.csv `accepted_variants`, `|` separated) come in two forms:
- a full alternative sentence: "அவங்க வந்தாங்க"
- a word swap "formal=colloquial": "அவர்கள்=அவங்க"
Every combination is tried and the reference closest to the hypothesis is used,
so a variant can only make a score better, never worse.

CER counts Unicode code points (as jiwer does), including spaces.
"""

import itertools
import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

import jiwer
import numpy as np

from kuralcheck.text.normalize import normalize
from kuralcheck.text.numbers import extract_numbers

MAX_REFERENCES = 256
N_RESAMPLES = 1000
SEED = 42


@dataclass(frozen=True)
class UtteranceScore:
    reference: str  # normalised reference actually used (closest variant)
    hypothesis: str  # normalised hypothesis
    char_edits: int
    char_ref: int
    word_edits: int
    word_ref: int
    num_matched: int
    num_ref: int


@dataclass(frozen=True)
class CI:
    value: float
    low: float
    high: float
    n: int


def expand_references(text: str, accepted_variants: Sequence[str] = ()) -> list[str]:
    """Normalised reference candidates: the text, full-sentence variants, and word swaps."""
    sentences = [normalize(text)]
    swaps: dict[str, set[str]] = {}
    for v in accepted_variants:
        if "=" in v:
            formal, _, colloquial = v.partition("=")
            swaps.setdefault(normalize(formal), set()).add(normalize(colloquial))
        elif v.strip():
            sentences.append(normalize(v))

    refs: list[str] = []
    for sent in dict.fromkeys(sentences):
        options = [[w, *sorted(swaps.get(w, ()))] for w in sent.split()]
        for combo in itertools.islice(itertools.product(*options), MAX_REFERENCES):
            refs.append(" ".join(combo))
    return list(dict.fromkeys(refs))


def _edits(ref: str, hyp: str) -> tuple[int, int]:
    """(character edits, word edits) between normalised strings."""
    if not ref:
        return len(hyp), len(hyp.split())
    c = jiwer.process_characters(ref, hyp)
    w = jiwer.process_words(ref, hyp)
    return (
        c.substitutions + c.deletions + c.insertions,
        w.substitutions + w.deletions + w.insertions,
    )


def number_matches(reference: str, hypothesis: str) -> tuple[int, int]:
    """(numbers recovered exactly, numbers in reference); digits and number words both count."""
    ref_nums = Counter(extract_numbers(reference))
    hyp_nums = Counter(extract_numbers(hypothesis))
    return sum((ref_nums & hyp_nums).values()), sum(ref_nums.values())


def score_utterance(
    reference: str, hypothesis: str, accepted_variants: Sequence[str] = ()
) -> UtteranceScore:
    hyp = normalize(hypothesis)
    best: tuple[int, int, str] | None = None
    for ref in expand_references(reference, accepted_variants):
        ce, we = _edits(ref, hyp)
        if best is None or (ce, we) < best[:2]:
            best = (ce, we, ref)
    assert best is not None
    char_edits, word_edits, ref = best
    matched, total = number_matches(reference, hypothesis)
    return UtteranceScore(
        reference=ref,
        hypothesis=hyp,
        char_edits=char_edits,
        char_ref=len(ref),
        word_edits=word_edits,
        word_ref=len(ref.split()),
        num_matched=matched,
        num_ref=total,
    )


def _ratio(num: int, den: int) -> float:
    return num / den if den else math.nan


def corpus_cer(scores: Sequence[UtteranceScore]) -> float:
    """Total character edits / total reference characters (not a mean of per-utterance CERs)."""
    return _ratio(sum(s.char_edits for s in scores), sum(s.char_ref for s in scores))


def corpus_wer(scores: Sequence[UtteranceScore]) -> float:
    return _ratio(sum(s.word_edits for s in scores), sum(s.word_ref for s in scores))


def corpus_number_accuracy(scores: Sequence[UtteranceScore]) -> float | None:
    total = sum(s.num_ref for s in scores)
    return sum(s.num_matched for s in scores) / total if total else None


def bootstrap_ci(
    scores: Sequence[UtteranceScore],
    statistic: Callable[[Sequence[UtteranceScore]], float | None],
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    confidence: float = 0.95,
) -> CI:
    """Percentile bootstrap over utterances."""
    n = len(scores)
    value = statistic(scores)
    if n == 0 or value is None:
        return CI(math.nan, math.nan, math.nan, n)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    stats = np.array(
        [s if (s := statistic([scores[i] for i in row])) is not None else math.nan for row in idx],
        dtype=float,
    )
    alpha = (1 - confidence) / 2
    low, high = np.nanpercentile(stats, [100 * alpha, 100 * (1 - alpha)])
    return CI(float(value), float(low), float(high), n)


def summarize(scores: Sequence[UtteranceScore]) -> dict:
    """CER, WER and number accuracy with 95% CIs and n, ready for results JSON."""
    with_numbers = [s for s in scores if s.num_ref > 0]
    return {
        "n": len(scores),
        "cer": asdict(bootstrap_ci(scores, corpus_cer)),
        "wer": asdict(bootstrap_ci(scores, corpus_wer)),
        "number_accuracy": (
            asdict(bootstrap_ci(with_numbers, corpus_number_accuracy)) if with_numbers else None
        ),
    }
