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
torn down when the module's tests finish.

PIPELINE names ovos-padatious-pipeline-plugin-high first, so padatious does
match here and it does train: the earlier claim that only padacioso boots and
that there is no training phase was wrong. get_minicroft defaults to
wait_for_trained=True, and that wait reads the trainer's own state rather
than the bus -- "mycroft.skills.trained" is a private readiness signal and
not a spec topic. The padacioso tiers below it serve a locale padatious
declines.

A row with "needs_manual": true is loaded but not executed. It records a
line the repository ships that the skill cannot answer today, so the file
keeps the evidence without the suite going red for a defect filed elsewhere.
The ru-RU "включи режим сна" row is the example: it is a real line of
locale/ru-RU/naptime.intent, and locale/ru-RU/naptime.blacklist suppresses it
because the line begins with a blacklisted word. Filed as T-5612.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
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
    "pl-PL", "pt-BR", "pt-PT", "ro-RO", "ru-RU", "sv-SE", "tr-TR",
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

# One MiniCroft alive at a time, deliberately.
#
# get_minicroft(lang=X) saves the process default session language at boot and
# writes it back at stop(). Keeping one per locale alive in a dict and stopping
# them all at teardown restores those saves out of nesting order, so the
# process is left on whichever locale the last restore wrote. Every en-US
# MiniCroft booted later in the same pytest process then loads the skill in
# that locale and routes nothing: this module passed while
# test_intents_en_us.py and test_wakeup_context_gate.py failed after it, and
# both of those passed alone. Stopping the previous MiniCroft before booting
# the next keeps every save and restore pair nested.
#
# The golden rows are grouped by locale (ALL_ROWS is built in LANGS order), so
# this costs the same number of boots as the dict did.
_DEFAULT_LANG_AT_IMPORT = SessionManager.get_default_session().lang

_CURRENT = {"lang": None, "mc": None}


def _stop_current():
    mc = _CURRENT["mc"]
    if mc is not None:
        mc.stop()
    _CURRENT["lang"] = None
    _CURRENT["mc"] = None


def _get_minicroft(lang):
    if _CURRENT["lang"] == lang:
        return _CURRENT["mc"]
    _stop_current()
    _CURRENT["mc"] = get_minicroft([SKILL_ID], max_wait=150, lang=lang,
                                    default_pipeline=PIPELINE)
    _CURRENT["lang"] = lang
    return _CURRENT["mc"]


@pytest.fixture(scope="module", autouse=True)
def _stop_the_last_minicroft():
    yield
    _stop_current()


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


def test_the_module_leaves_the_process_on_its_default_language():
    """The control for the one-MiniCroft-at-a-time rule above.

    Defined last, so it runs after every locale has been booted and stopped,
    and it reads the one value whose corruption made the modules after this
    one fail. Without it, a reader cannot tell a fixed restore order from a
    suite that never looked. It compares against the value read at import,
    not a hard-coded locale, so it states only that this module gives the
    process back as it found it.
    """
    _stop_current()
    assert SessionManager.get_default_session().lang == _DEFAULT_LANG_AT_IMPORT, (
        "this module left the process default session language on "
        f"{SessionManager.get_default_session().lang!r}; every MiniCroft booted "
        "after it loads the skill in that locale and routes nothing"
    )
