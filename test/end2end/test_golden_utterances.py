"""Golden rows route to their intent on the m2v prototype pipeline, and
negative rows reach no intent of this skill."""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovoscope import CaptureSession
from ovoscope.routing import TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"
SLEEP_CONTEXT = f"{SKILL_ID}:sleeping_state"
END2END_DIR = Path(__file__).parent
DEFAULT_LANG_AT_IMPORT = SessionManager.get_default_session().lang


def _rows(prefix):
    rows = []
    for path in sorted(END2END_DIR.glob(f"{prefix}*.jsonl")):
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    return rows


GOLDEN = _rows("golden_utterances_")
NEGATIVE = _rows("negative_utterances_")
_booted = {}


def _message(utterance, lang, session):
    return Message("recognizer_loop:utterance", {"utterances": [utterance], "lang": lang},
                   {"lang": lang, "session": session.serialize()})


def _fresh_session(lang):
    session = Session(f"golden-{lang}")
    session.lang = lang
    return session


def _sleeping_session(minicroft, lang):
    """Put the skill to sleep through its own handler and return that session.

    ``wake_up.intent`` requires the ``sleeping_state`` context, so its rows
    run in a session that a ``naptime.intent`` row put to sleep.
    """
    for row in GOLDEN:
        if row["lang"] != lang or row["intent_label"] != "naptime.intent":
            continue
        capture = CaptureSession(minicroft, eof_msgs=["ovos.utterance.handled"])
        capture.capture(_message(row["utterance"], lang, _fresh_session(lang)), timeout=30)
        for message in reversed(capture.finish()):
            if message.msg_type == "ovos.utterance.handled":
                handled = Session.deserialize(message.context["session"])
                if SLEEP_CONTEXT in (handled.intent_context or {}):
                    return handled
                break
    return _fresh_session(lang)


@pytest.fixture(scope="module")
def engine_for():
    def engine(lang):
        if lang not in _booted:
            for minicroft, _ in _booted.values():
                minicroft.stop()
            _booted.clear()
            minicroft = get_prototype_minicroft([SKILL_ID], lang=lang)
            _booted[lang] = (minicroft, _sleeping_session(minicroft, lang))
        minicroft, sleeping = _booted[lang]
        return minicroft.intents.pipeline_plugins["ovos-m2v-prototype-pipeline"], sleeping
    yield engine
    for minicroft, _ in _booted.values():
        minicroft.stop()


def _routed(engine, utterance, lang, session):
    match = engine.match_low([utterance], lang, _message(utterance, lang, session))
    return [match.match_type] if match else []


def _row_id(row):
    return f"{row['lang']}:{row['utterance']}"


@pytest.mark.parametrize("row", GOLDEN, ids=_row_id)
def test_golden_row_routes_to_its_intent(engine_for, row):
    engine, sleeping = engine_for(row["lang"])
    session = sleeping if row["intent_label"] == "wake_up.intent" else _fresh_session(row["lang"])
    fired = _routed(engine, row["utterance"], row["lang"], session)
    TALLY.assert_routed(row["utterance"], f"{SKILL_ID}:{row['intent_label']}", fired)


@pytest.mark.parametrize("row", NEGATIVE, ids=_row_id)
def test_negative_row_reaches_no_intent_of_the_skill(engine_for, row):
    engine, _ = engine_for(row["lang"])
    fired = _routed(engine, row["utterance"], row["lang"], _fresh_session(row["lang"]))
    TALLY.assert_not_routed(row["utterance"],
                            [t for t in fired if t.startswith(f"{SKILL_ID}:")], fired)


def test_every_negative_file_has_a_golden_file():
    negative = {row["lang"] for row in NEGATIVE}
    golden = {row["lang"] for row in GOLDEN}
    assert negative <= golden, f"negatives without golden rows: {sorted(negative - golden)}"


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_the_module_leaves_the_process_on_its_default_language():
    """A MiniCroft booted in one locale writes the process default language
    back when it stops."""
    for minicroft, _ in _booted.values():
        minicroft.stop()
    _booted.clear()
    assert SessionManager.get_default_session().lang == DEFAULT_LANG_AT_IMPORT
