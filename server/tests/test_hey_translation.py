import pytest
from sarvagyan_server.providers.mymemory import MyMemoryTranslator, choose_translation
from sarvagyan_server.providers import phrasebook


@pytest.mark.asyncio
async def test_hey_does_not_translate_to_love_you():
    # 1. Test phrasebook lookup for hey
    pb_res = phrasebook.lookup("hey", "en-IN", "ta-IN")
    assert pb_res == "ஹேய்"
    assert "love" not in pb_res.lower() and "டார்லிங்" not in pb_res

    # 2. Test choose_translation against simulated MyMemory troll response
    troll_response = {
        "responseData": {
            "translatedText": "ஐ லவ் யூ டார்லிங்",
            "match": 1
        },
        "matches": [
            {
                "id": "428244254",
                "segment": "hey",
                "translation": "ஐ லவ் யூ டார்லிங்",
                "created-by": "Public Web",
                "match": 1
            },
            {
                "id": "424511014",
                "segment": "hey",
                "translation": "ஏய்",
                "created-by": "MT!",
                "match": 0.99
            }
        ]
    }
    chosen = choose_translation("hey", "ta", troll_response)
    # Must reject "ஐ லவ் யூ டார்லிங்" and pick clean translation "ஏய்"
    assert chosen != "ஐ லவ் யூ டார்லிங்"
    assert chosen == "ஏய்"

    # 3. Test full translator
    translator = MyMemoryTranslator()
    try:
        tr_res = await translator.translate("hey", "en-IN", "ta-IN")
        assert tr_res != "ஐ லவ் யூ டார்லிங்"
        assert "love" not in tr_res.lower()
        print(f"\nFinal translation of 'hey': {tr_res}")
    finally:
        await translator.close()

