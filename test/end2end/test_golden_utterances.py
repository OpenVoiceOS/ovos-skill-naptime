"""Golden-utterance end-to-end coverage for ovos-skill-naptime (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-naptime.openvoiceos"``. One shared ``MiniCroft``
(module-scoped fixture) is booted for the whole suite; every row is its own
parametrized test item.

``handle_wakeup`` is bound to ``IntentBuilder("WakeUp").require("wakeup")
.require("sleeping_state")`` -- it only matches once the skill has set the
``sleeping_state`` adapt context, which happens inside
``handle_go_to_sleep``. So the "wake up" golden row is run in a session that
has already been put to sleep in the same session_id, mirroring how the
skill is actually used (you can't wake up a device that was never asleep).
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-low",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "mycroft.audio.play_sound",
    "mycroft.awoken",
    "recognizer_loop:sleep",
    "recognizer_loop:wake_up",
    "mycroft.volume.mute",
    "mycroft.volume.unmute",
    "configuration.patch",
    "mycroft.skill.set_context",
    "mycroft.skill.remove_context",
    "add_context",
    "remove_context",
    "enclosure.eyes.brightness",
    "enclosure.eyes.level",
    "enclosure.eyes.look",
    "enclosure.eyes.reset",
    "enclosure.eyes.blink",
    "enclosure.eyes.on",
    "enclosure.eyes.off",
    "enclosure.eyes.narrow",
    "enclosure.mouth.reset",
    "enclosure.mouth.text",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices,
# picked for lexical overlap with naptime's "sleep"/"nap"/"wake" vocabulary.
NEGATIVE_UTTERANCES = [
    ("what time is it", "ovos-skill-date-time.openvoiceos"),
    ("set an alarm for 7am", "ovos-skill-alarm.openvoiceos"),
    ("set a timer for 5 minutes", "ovos-skill-alerts.openvoiceos"),
    ("play some music", "ovos-skill-music.openvoiceos"),
    ("turn off the lights", "ovos-skill-homeassistant.openvoiceos"),
    ("what's the weather", "ovos-skill-weather.openvoiceos"),
    ("stop the timer", "ovos-skill-alerts.openvoiceos"),
]


def _candidates(skill_id: str, intent_label: str) -> set:
    """padatious/padacioso plugin versions register the matched-intent bus
    event under different normalizations of the ``.intent`` filename
    basename -- candidates cover both the suffixed and unsuffixed forms so
    the suite isn't pinned to whichever pipeline plugin happens to be
    installed. Adapt intent names (eg. "WakeUp") have no ``.intent``
    suffix to strip."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{intent_label}", f"{skill_id}:{base}"}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


GOLDEN_ROWS = [pytest.param(r, id=r["utterance"]) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _session(session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents defaults to None on a fresh Session, which crashes
    # the padacioso pipeline (NoneType membership test) - force an empty list.
    session.blacklisted_intents = []
    return session


def _fire(mc, text, session):
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, ignore_messages=_IGNORE)
    capture.capture(utterance, timeout=30)
    messages = capture.finish()
    return [m.msg_type for m in messages], _last_session(messages, session)


def _last_session(messages, fallback):
    # A client forwards the session it last received from the bus, not a
    # stale local snapshot -- server-side context (eg. skill set_context)
    # lives only on the SessionManager copy, and re-sending an older
    # object overwrites it under last-writer-wins.
    for m in reversed(messages):
        if m.msg_type == "ovos.utterance.handled":
            raw = m.context.get("session")
            if raw:
                return Session.deserialize(raw)
    return fallback


def _types(mc, text, session_id):
    types, _ = _fire(mc, text, _session(session_id))
    return types


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    candidates = _candidates(SKILL_ID, row["intent_label"])
    session_id = f"golden-{_golden_id(row)}"
    if row["utterance"] == "wake up":
        # WakeUp requires the "sleeping_state" adapt context, set only after
        # a successful go-to-sleep in the same session -- precondition the
        # session the same way a real user would (go to sleep, then wake up).
        session = _session(session_id)
        _, session = _fire(minicroft, "go to sleep", session)
        types, _ = _fire(minicroft, row["utterance"], session)
    else:
        types = _types(minicroft, row["utterance"], session_id)
    assert any(t in candidates for t in types), (
        f"{row['utterance']!r}: expected one of {sorted(candidates)!r}, got {types!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    types = _types(minicroft, text, f"negative-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"
