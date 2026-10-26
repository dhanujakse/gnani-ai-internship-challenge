import pytest

from kuralcheck.text.numbers import extract_numbers, parse_number_word


@pytest.mark.parametrize(
    ("word", "value"),
    [
        ("ஒன்று", 1),
        ("இரண்டு", 2),
        ("ரெண்டு", 2),
        ("நாலு", 4),
        ("அஞ்சு", 5),
        ("பத்து", 10),
        ("பன்னிரண்டு", 12),
        ("பதினைந்து", 15),
        ("பத்தொன்பது", 19),
        ("இருபது", 20),
        ("இருபத்தைந்து", 25),
        ("இருபத்திமூன்று", 23),
        ("முப்பத்திரண்டு", 32),
        ("தொண்ணூற்றொன்பது", 99),
        ("நூறு", 100),
        ("ஐநூறு", 500),
        ("ஆயிரம்", 1000),
        ("இரண்டாயிரம்", 2000),
        ("பத்தாயிரம்", 10000),
    ],
)
def test_single_word_values(word: str, value: int) -> None:
    assert parse_number_word(word) == value


def test_non_number_word() -> None:
    assert parse_number_word("கடை") is None


def test_spaced_compounds() -> None:
    assert extract_numbers("இருபத்தி ஐந்து ரூபாய்") == [25]
    assert extract_numbers("நூற்று இருபது பேர்") == [120]
    assert extract_numbers("ஆயிரத்து ஐநூறு ரூபாய்") == [1500]
    assert extract_numbers("இரண்டு லட்சம் ஐம்பது ஆயிரம்") == [250000]
    assert extract_numbers("இரண்டு லட்சம் ஐம்பதாயிரம்") == [250000]
    assert extract_numbers("இரண்டு லட்சத்து ஐம்பதாயிரம் ரூபாய்") == [250000]
    assert extract_numbers("பன்னிரண்டாயிரம் ரூபாய்") == [12000]


def test_separate_numbers_stay_separate() -> None:
    # "ten thirty" (10:30) is two numbers, not 40
    assert extract_numbers("பத்து முப்பது மணிக்கு") == [10, 30]


def test_digits() -> None:
    assert extract_numbers("10:30 மணிக்கு ₹1,500 கொடுங்க") == [10, 30, 1500]


def test_mixed_digits_and_words() -> None:
    assert extract_numbers("3 கிலோ அரிசி, நாலு பாக்கெட் பால்") == [3, 4]


def test_no_numbers() -> None:
    assert extract_numbers("நாளைக்கு வாங்க") == []
