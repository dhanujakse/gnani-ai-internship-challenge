import math

import numpy as np
import pytest

from kuralcheck.metrics import (
    bootstrap_ci,
    corpus_cer,
    corpus_number_accuracy,
    corpus_wer,
    score_utterance,
    summarize,
)


def test_identical_strings_score_zero() -> None:
    s = score_utterance("நான் நாளைக்கு வருவேன்", "நான் நாளைக்கு வருவேன்")
    assert s.char_edits == 0 and s.word_edits == 0
    assert corpus_cer([s]) == 0.0 and corpus_wer([s]) == 0.0


def test_punctuation_only_difference_scores_zero() -> None:
    s = score_utterance("சரி, போலாம்.", "சரி போலாம்")
    assert corpus_cer([s]) == 0.0


def test_zwj_difference_scores_zero() -> None:
    s = score_utterance("க்ஷேமம்", "க்‍ஷேமம்")
    assert corpus_cer([s]) == 0.0


def test_colloquial_without_variant_is_penalised() -> None:
    # Gnani's own example: colloquial "avanga" vs formal "avargal".
    s = score_utterance("அவர்கள் வந்தாங்க", "அவங்க வந்தாங்க")
    assert corpus_wer([s]) == pytest.approx(0.5)  # 1 of 2 words wrong
    assert 0 < corpus_cer([s]) < corpus_wer([s])  # CER punishes it less


def test_colloquial_with_sentence_variant_is_correct() -> None:
    s = score_utterance("அவர்கள் வந்தாங்க", "அவங்க வந்தாங்க", ["அவங்க வந்தாங்க"])
    assert corpus_cer([s]) == 0.0 and corpus_wer([s]) == 0.0


def test_colloquial_with_word_variant_is_correct() -> None:
    s = score_utterance(
        "அவர்கள் நாளைக்கு வருவார்கள்",
        "அவங்க நாளைக்கு வருவாங்க",
        ["அவர்கள்=அவங்க", "வருவார்கள்=வருவாங்க"],
    )
    assert corpus_cer([s]) == 0.0


def test_variant_never_makes_score_worse() -> None:
    base = score_utterance("அவர்கள் வந்தாங்க", "அவர்கள் வந்தாங்க")
    with_variant = score_utterance("அவர்கள் வந்தாங்க", "அவர்கள் வந்தாங்க", ["அவங்க வந்தாங்க"])
    assert with_variant.char_edits == base.char_edits == 0


def test_digits_vs_words_number_is_recovered() -> None:
    s = score_utterance("பத்து ரூபாய் கொடுங்க", "10 ரூபாய் கொடுங்க")
    assert s.num_ref == 1 and s.num_matched == 1
    assert corpus_number_accuracy([s]) == 1.0


def test_wrong_number_is_not_recovered() -> None:
    s = score_utterance("இருபத்தைந்து ரூபாய்", "35 ரூபாய்")
    assert corpus_number_accuracy([s]) == 0.0


def test_number_accuracy_none_without_numbers() -> None:
    s = score_utterance("வணக்கம்", "வணக்கம்")
    assert corpus_number_accuracy([s]) is None


def test_corpus_cer_is_dataset_level_not_mean_of_ratios() -> None:
    long_ok = score_utterance("அ" * 9 + "ஆ", "அ" * 9 + "ஆ")  # 0 / 10
    short_bad = score_utterance("இ", "ஈ")  # 1 / 1
    # mean of ratios would be 0.5; dataset level is 1/11
    assert corpus_cer([long_ok, short_bad]) == pytest.approx(1 / 11)


def test_empty_hypothesis_is_all_deletions() -> None:
    s = score_utterance("சரி போலாம்", "")
    assert corpus_cer([s]) == 1.0 and corpus_wer([s]) == 1.0


def _fake_scores(n: int, seed: int) -> list:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ref = "அஆஇஈஉ ஊஎஏஐ"
        hyp = "".join(c if rng.random() > 0.2 else "ஒ" for c in ref)
        out.append(score_utterance(ref, hyp))
    return out


def test_bootstrap_ci_contains_point_estimate_and_reports_n() -> None:
    scores = _fake_scores(50, seed=1)
    ci = bootstrap_ci(scores, corpus_cer)
    assert ci.n == 50
    assert ci.low <= ci.value <= ci.high


def test_bootstrap_is_reproducible() -> None:
    scores = _fake_scores(30, seed=2)
    assert bootstrap_ci(scores, corpus_cer) == bootstrap_ci(scores, corpus_cer)


def test_ci_width_shrinks_as_n_grows() -> None:
    small = bootstrap_ci(_fake_scores(20, seed=3), corpus_cer)
    large = bootstrap_ci(_fake_scores(500, seed=3), corpus_cer)
    assert (large.high - large.low) < (small.high - small.low)


def test_summarize_shape() -> None:
    scores = _fake_scores(10, seed=4) + [score_utterance("பத்து ரூபாய்", "10 ரூபாய்")]
    summary = summarize(scores)
    assert summary["n"] == 11
    assert set(summary) >= {"n", "cer", "wer", "number_accuracy"}
    assert summary["number_accuracy"]["n"] == 1  # only one utterance has numbers
    assert not math.isnan(summary["cer"]["low"])


def test_summarize_without_numbers_has_null_number_accuracy() -> None:
    summary = summarize([score_utterance("வணக்கம்", "வணக்கம்")])
    assert summary["number_accuracy"] is None
