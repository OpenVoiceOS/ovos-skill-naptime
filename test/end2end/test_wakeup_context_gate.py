"""wake_up.intent declares requires_context=["sleeping_state"] -- it must be
invisible to the pipelines in a fresh session that never went to sleep, and
must match once "go to sleep" has set that context.

These are general context-gate regression checks in en-US. The per-locale
golden coverage is test_golden_utterances.py.
"""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"
LANG = "en-US"

NAPTIME = f"{SKILL_ID}:naptime"
WAKE_UP = f"{SKILL_ID}:wake_up"


def _session(session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(PIPELINE)
    session.blacklisted_intents = []
    return session


def _last_session(messages, fallback):
    for m in reversed(messages):
        if m.msg_type == "ovos.utterance.handled":
            raw = m.context.get("session")
            if raw:
                return Session.deserialize(raw)
    return fallback


@pytest.fixture(scope="module")
def minicroft():
    mc = get_prototype_minicroft([SKILL_ID], max_wait=150)
    yield mc
    mc.stop()


def _fire(mc, text, session):
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc, ignore_messages=[])
    capture.capture(utterance, timeout=30)
    messages = capture.finish()
    return [m.msg_type for m in messages], _last_session(messages, session)


@pytest.mark.timeout(60)
def test_wakeup_requires_sleeping_state_context(minicroft):
    fresh_types, _ = _fire(minicroft, "wake up", _session("gate-fresh-wake-up"))
    TALLY.assert_not_routed("wake up", [WAKE_UP], fresh_types)

    session = _session("gate-sleep-then-wake")
    sleep_types, session = _fire(minicroft, "go to sleep", session)
    TALLY.assert_routed("go to sleep", NAPTIME, sleep_types)
    asleep_types, _ = _fire(minicroft, "wake up", session)
    TALLY.assert_routed("wake up", WAKE_UP, asleep_types)
