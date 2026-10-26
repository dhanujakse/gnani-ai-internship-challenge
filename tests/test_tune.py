import pytest

from kuralcheck.fixlayer.tune import edit_ratio, mine_bias_words, tune_rules
from kuralcheck.metrics import score_utterance
from kuralcheck.runner import score_fields


def rec(ref: str, hyp: str, setting: str = "F2", variants: tuple = (), split: str = "dev", sid: str = "s") -> dict:
    sc = score_utterance(ref, hyp, variants)
    return {"reference": ref, "accepted_variants": list(variants), "hypothesis_raw": hyp, "setting": setting,
            "split": split, "error": None, "sentence_id": sid, **score_fields(sc)}  # fmt: skip


def test_edit_ratio() -> None:
    assert edit_ratio("சர்ஜ்", "சார்ஜ்") < 0.4
    assert edit_ratio("போகணும்", "போனோம்") > 0.4
    assert edit_ratio("abc", "abc") == 0


def test_refuses_test_split() -> None:
    with pytest.raises(ValueError, match="dev-split"):
        tune_rules([rec("சரி", "சரி", split="test")])
    with pytest.raises(ValueError):
        mine_bias_words([rec("சரி", "சரி", setting="F1", split="test")])


def test_keeps_currency_rule_and_rejects_harmful_ones() -> None:
    recs = [
        rec("ஒரு கிலோ தக்காளி இருபத்தைந்து ரூபாய்", "ஒரு கிலோ தக்காளி ₹25", variants=("இருபத்தைந்து=25",)),
        rec("வாடகை பன்னிரண்டாயிரம் ரூபாய்", "வாடகை ₹12,000", variants=("பன்னிரண்டாயிரம்=12000",)),
    ]
    lex, report = tune_rules(recs)
    notes = [fr.note for fr in report.format_kept]
    assert any("currency" in n for n in notes)
    assert report.final_edits == 0 < report.base_edits
    assert lex.apply("₹25") == "25 ரூபாய்"


def test_mines_spelling_fix_but_not_mishearing() -> None:
    recs = [rec("என் போன் சார்ஜ் ஆகவில்லை", "என் போன் சர்ஜ் ஆகவில்லை", sid=f"s{i}") for i in range(2)]
    recs += [rec("திருப்பூருக்குப் போனோம்", "திருப்பூருக்குப் போகணும்", sid=f"p{i}") for i in range(3)]
    _, report = tune_rules(recs)
    pairs = {(r.pattern, r.replacement) for r in report.word_kept}
    assert ("சர்ஜ்", "சார்ஜ்") in pairs
    assert not any(p == "போகணும்" for p, _ in pairs)  # different word: never "fixed" by memorising


def test_no_harm_rule() -> None:
    # "1 " -> "ஒரு " helps the first record but hurts the second, so it must be rejected
    recs = [rec("ஒரு கிலோ", "1 கிலோ"), rec("1 கிலோ", "1 கிலோ")]
    _, report = tune_rules(recs)
    assert not any("ஒரு" in fr.note for fr in report.format_kept)


def test_bias_words_from_f1_errors() -> None:
    recs = [rec("அவங்க வந்தாங்க", "அவர்கள் வந்தாங்க", setting="F1", sid=f"x{i}") for i in range(3)]
    recs.append(rec("சரி", "சரி", setting="F0"))
    assert mine_bias_words(recs) == ["அவங்க"]
