"""wake_up.intent declares requires_context=["sleeping_state"] -- it must be
invisible to the pipelines in a fresh session that never went to sleep, and
must match once "go to sleep" has set that context.

Split out of the former test_golden_utterances.py (en-US only), which is
now test_golden_utterances_multilang.py -- these are general context-gate
regression checks, not locale golden coverage, and stay en-US.
"""
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

_FILE_INTENT_ONLY_PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
]


def _candidates(skill_id: str, intent_label: str) -> set:
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{intent_label}", f"{skill_id}:{base}"}


def _session(session_id, pipeline):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(pipeline)
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
    mc = get_minicroft([SKILL_ID], max_wait=150)
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
    candidates = _candidates(SKILL_ID, "wake_up.intent")

    fresh_types, _ = _fire(minicroft, "wake up", _session("gate-fresh-wake-up", _PIPELINE))
    claimed_fresh = any(t in candidates for t in fresh_types)
    assert not claimed_fresh, (
        f"'wake up' in a fresh session must NOT match wake_up, got {fresh_types!r}"
    )

    session = _session("gate-sleep-then-wake", _PIPELINE)
    _, session = _fire(minicroft, "go to sleep", session)
    asleep_types, _ = _fire(minicroft, "wake up", session)
    assert any(t in candidates for t in asleep_types), (
        f"'wake up' after 'go to sleep' must match wake_up, got {asleep_types!r}"
    )


@pytest.mark.timeout(60)
def test_wakeup_file_intent_gate_without_adapt(minicroft):
    candidates = _candidates(SKILL_ID, "wake_up.intent")

    fresh_types, _ = _fire(minicroft, "wake up", _session("gate-fresh-wake-up-no-adapt", _FILE_INTENT_ONLY_PIPELINE))
    claimed_fresh = any(t in candidates for t in fresh_types)
    assert not claimed_fresh, (
        f"'wake up' in a fresh session must NOT match wake_up, got {fresh_types!r}"
    )

    session = _session("gate-sleep-then-wake-no-adapt", _FILE_INTENT_ONLY_PIPELINE)
    _, session = _fire(minicroft, "go to sleep", session)
    asleep_types, _ = _fire(minicroft, "wake up", session)
    assert any(t in candidates for t in asleep_types), (
        f"'wake up' after 'go to sleep' must match wake_up, got {asleep_types!r}"
    )
