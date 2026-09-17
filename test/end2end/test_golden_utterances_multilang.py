"""Multilingual golden-utterance end-to-end coverage for
ovos-skill-naptime.

test_intents_en_us.py / test_golden_utterances.py (superseded by this file)
only exercised en-US. This skill registers two Padatious/Padacioso
file-intents (naptime.intent, wake_up.intent); every locale under locale/
ships real .intent content for both. Each golden row is a literal
resolution of that locale's own .intent template lines -- (a|b)
alternatives and [a|b]/(x|) optional groups resolve to one concrete
choice -- no translated or invented prose is introduced.

wake_up.intent is declared with requires_context=["sleeping_state"] -- it
only matches once naptime.intent's handler has set that context. Every
wake_up.intent golden row is therefore run in a session that first fired a
"go to sleep"-shaped naptime.intent utterance (that locale's own first
naptime.intent line), mirroring how the skill is actually used -- see
test_wakeup_context_gate.py for the general context-gate regression checks
this suite does not repeat.

Unlike ovos-skill-alerts' shared-MiniCroft-with-secondary-langs approach
(blocked by ovoscope#179 at multi-locale scale), this suite follows the
ovos-skill-date-time per-locale pattern (test/end2end/test_intents_it_it.py
on that repo's dev branch): one MiniCroft is booted per locale, in turn,
torn down when the module's tests finish. Only the pure-Python, swig-free
padacioso template engine is booted (no padatious training phase, so no
"mycroft.skills.trained" wait across many locales).
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"

PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

END2END_DIR = Path(__file__).parent

LANGS = [
    "ca-ES", "cs-CZ", "da-DK", "de-DE", "el-GR", "en-US", "es-ES", "eu-ES",
    "fa-IR", "fr-FR", "gl-ES", "hu-HU", "it-IT", "kab", "nl-NL", "oc-FR",
    "pl-PL", "pt-BR", "pt-PT", "ro-RO", "ru-RU", "sv-SE",
]

# the first naptime.intent golden row loaded for that locale is used as the
# "go to sleep" precondition for its wake_up.intent rows.
_SLEEP_UTTERANCE = {}

CROSS_LANG_NEGATIVES = [
    ("what time is it", "de-DE", "other-skill (date-time) phrasing, german session"),
    ("play some music", "fr-FR", "other-skill (music) phrasing, french session"),
    ("what's the weather", "es-ES", "other-skill (weather) phrasing, spanish session"),
]


def _candidates(skill_id: str, intent_label: str) -> set:
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{intent_label}", f"{skill_id}:{base}"}


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
            if row["intent_label"] == "naptime.intent" and lang not in _SLEEP_UTTERANCE:
                _SLEEP_UTTERANCE[lang] = row["utterance"]
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _golden_id(row):
    return f"{row['lang']}-{row['intent_label']}-{row['utterance']}"


GOLDEN_ROWS = [pytest.param(r, id=_golden_id(r)) for r in ALL_ROWS]

_MINICROFTS = {}


def _get_minicroft(lang):
    mc = _MINICROFTS.get(lang)
    if mc is None:
        mc = get_minicroft([SKILL_ID], max_wait=150, lang=lang,
                            default_pipeline=PIPELINE)
        _MINICROFTS[lang] = mc
    return mc


@pytest.fixture(scope="module", autouse=True)
def _stop_all_minicrofts():
    yield
    for mc in _MINICROFTS.values():
        mc.stop()
    _MINICROFTS.clear()


def _session(lang, session_id):
    session = Session(session_id)
    session.lang = lang
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


def _fire(mc, text, lang, session, *, full_capture=False):
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    # the precondition ("go to sleep") call needs the full capture (no
    # eof_msgs cutoff) so ovos.utterance.handled -- which carries the
    # server-updated session with sleeping_state set -- is actually
    # captured; cutting off at handler-start would return the session
    # unchanged and every wake_up.intent row would then run in a session
    # that was never put to sleep.
    # ovoscope's CaptureSession requires an iterable eof_msgs (None raises
    # TypeError) -- "ovos.utterance.handled" is the message that carries the
    # server-updated session (with sleeping_state set), so waiting for it
    # is the full capture the sleep precondition needs.
    eof_msgs = ["ovos.utterance.handled"] if full_capture else ["mycroft.skill.handler.start"]
    capture = CaptureSession(mc, eof_msgs=eof_msgs)
    capture.capture(utterance, timeout=30)
    messages = capture.finish()
    return [m.msg_type for m in messages], _last_session(messages, session)


@pytest.mark.timeout(180)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance_multilang(row):
    mc = _get_minicroft(row["lang"])
    candidates = _candidates(SKILL_ID, row["intent_label"])
    session = _session(row["lang"], f"golden-{_golden_id(row)}")
    if row["intent_label"] == "wake_up.intent":
        sleep_utt = _SLEEP_UTTERANCE[row["lang"]]
        _, session = _fire(mc, sleep_utt, row["lang"], session, full_capture=True)
    types, _ = _fire(mc, row["utterance"], row["lang"], session)
    assert any(t in candidates for t in types), (
        f"[{row['lang']}] {row['utterance']!r}: expected one of {sorted(candidates)!r}, got {types!r}"
    )


@pytest.mark.timeout(180)
@pytest.mark.parametrize("negative", CROSS_LANG_NEGATIVES, ids=lambda n: f"{n[1]}-{n[0]}")
def test_cross_language_negative(negative):
    text, lang, _why = negative
    mc = _get_minicroft(lang)
    types, _ = _fire(mc, text, lang, _session(lang, f"negative-{lang}-{text}"))
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"[{lang}] {text!r} was incorrectly claimed by {SKILL_ID}"
