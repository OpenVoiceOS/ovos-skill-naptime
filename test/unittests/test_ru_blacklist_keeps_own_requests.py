"""The ru-RU blacklist must not suppress the naptime phrasings themselves.

The en-US blacklist stops media requests such as "play some sleep music". Its
ru-RU counterpart is "включи музыку". A bare "включи" also opens the intent's
own sample "включи режим сна".
"""
from pathlib import Path

import pytest
from ovos_m2v_pipeline import _word_sequence
from ovos_spec_tools.resources import LocaleResources
from padacioso import IntentContainer

LOCALE_DIR = Path(__file__).parents[2] / "locale"
RESOURCES = LocaleResources(str(LOCALE_DIR))
INTENT = "naptime"
LANG = "ru-RU"

OWN_REQUESTS = [
    "включи режим сна",
    "иди спать",
    "перейди в спящий режим",
]
MEDIA_REQUESTS = [
    "включи музыку для сна",
]


def _padacioso_label(utterance):
    container = IntentContainer()
    container.add_intent(INTENT, RESOURCES.load_intent(INTENT, LANG))
    container.exclude_keywords(INTENT, RESOURCES.load_blacklist(INTENT, LANG))
    return container.calc_intent(utterance)["name"]


def _m2v_suppressed(utterance):
    words = f" {_word_sequence(utterance)} "
    phrases = (_word_sequence(p) for p in RESOURCES.load_blacklist(INTENT, LANG))
    return any(f" {p} " in words for p in phrases if p)


@pytest.mark.parametrize("utterance", OWN_REQUESTS)
def test_padacioso_matches_own_request(utterance):
    assert _padacioso_label(utterance) == INTENT


@pytest.mark.parametrize("utterance", OWN_REQUESTS)
def test_m2v_does_not_suppress_own_request(utterance):
    assert not _m2v_suppressed(utterance)


@pytest.mark.parametrize("utterance", MEDIA_REQUESTS)
def test_media_request_is_suppressed(utterance):
    assert _m2v_suppressed(utterance)
