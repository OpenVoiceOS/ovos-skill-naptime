"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

``wake_up.intent`` declares ``requires_context=["sleeping_state"]``, so it
only matches on a device the skill put to sleep. Before the rows run, the
test sends the locale's ``naptime.intent`` rows through the MiniCroft until
the skill handles one and writes that context into the session. The
``wake_up.intent`` rows then run in that session, and the
``naptime.intent`` rows run in a fresh one, as a user says them.

Each locale must pass at least ``MIN_MATCH_RATE`` of its rows, and each
intent at least ``MIN_MATCHED_ROWS_PER_INTENT`` of its own rows. All rows run,
including rows marked ``needs_manual`` or ``machine_generated``, and the test
prints every row that misses with the intent that matched instead.

``negative_utterances_<lang>.jsonl`` holds requests for other skills (time,
weather, timers, alarms, music). In the same MiniCroft, each one must match
none of this skill's intents, unless ``NEGATIVE_KNOWN_CLAIMS`` names that
claim.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovoscope import M2V_PUBLISHED_MODEL, CaptureSession, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-naptime.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
SLEEP_CONTEXT = f"{SKILL_ID}:sleeping_state"
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# Every intent with rows in a locale must match at least this many of them,
# so the locale rate cannot hide an intent that never matches.
MIN_MATCHED_ROWS_PER_INTENT = 1
# A negative row that m2v claims in two runs is listed here by name, as
# {lang: {utterance: claimed_intent}}. Any other claim fails the locale.
NEGATIVE_KNOWN_CLAIMS = {}
END2END_DIR = Path(__file__).parent
DEFAULT_LANG_AT_IMPORT = SessionManager.get_default_session().lang


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVES = _rows_by_lang("negative_utterances")


def _utterance(text, lang, session):
    return Message("recognizer_loop:utterance", {"utterances": [text], "lang": lang},
                   {"lang": lang, "session": session.serialize()})


def _sleeping_session(minicroft, lang):
    """Put the skill to sleep through its own handler and return that session."""
    for row in ROWS[lang]:
        if row["intent_label"] != "naptime.intent":
            continue
        session = Session(f"golden-sleep-{lang}")
        session.lang = lang
        capture = CaptureSession(minicroft, eof_msgs=["ovos.utterance.handled"])
        capture.capture(_utterance(row["utterance"], lang, session), timeout=30)
        for message in reversed(capture.finish()):
            if message.msg_type == "ovos.utterance.handled":
                handled = Session.deserialize(message.context["session"])
                if SLEEP_CONTEXT in (handled.intent_context or {}):
                    return handled
                break
    pytest.fail(f"[{lang}] no naptime.intent row put the skill to sleep")


def _matched_intent(engine, utterance, lang, session):
    message = _utterance(utterance, lang, session)
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        sleeping = _sleeping_session(minicroft, lang)
        misses = []
        matched = Counter()
        for row in ROWS[lang]:
            expected = f"{SKILL_ID}:{row['intent_label'].removesuffix('.intent')}"
            if row["intent_label"] == "wake_up.intent":
                session = sleeping
            else:
                session = Session(f"golden-awake-{lang}")
                session.lang = lang
            got = _matched_intent(engine, row["utterance"], lang, session)
            if got == expected:
                matched[row["intent_label"]] += 1
            else:
                misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
        awake = Session(f"golden-negative-{lang}")
        awake.lang = lang
        known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
        claimed = []
        for row in NEGATIVES.get(lang, []):
            got = _matched_intent(engine, row["utterance"], lang, awake)
            if got and got.startswith(f"{SKILL_ID}:") and \
                    f"{SKILL_ID}:{known.get(row['utterance'], '').removesuffix('.intent')}" != got:
                claimed.append(f"{row['utterance']!r}: claimed by {got}")
    finally:
        minicroft.stop()
    rate = 1 - len(misses) / len(ROWS[lang])
    print(f"[{lang}] {rate:.1%} of {len(ROWS[lang])} rows match", *misses, sep="\n  ")
    starved = sorted(label for label in {row["intent_label"] for row in ROWS[lang]}
                     if matched[label] < MIN_MATCHED_ROWS_PER_INTENT)
    assert not starved, (
        f"[{lang}] intents with fewer than {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )
    if lang in NEGATIVES:
        print(f"[{lang}] {len(claimed)} of {len(NEGATIVES[lang])} negatives claimed", *claimed, sep="\n  ")
        assert not claimed, f"[{lang}] negatives claimed by this skill:\n  " + "\n  ".join(claimed)


def test_every_negative_file_has_a_golden_file():
    assert set(NEGATIVES) <= set(ROWS), sorted(set(NEGATIVES) - set(ROWS))


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_the_module_leaves_the_process_on_its_default_language():
    """A MiniCroft booted in one locale writes the process default language
    back when it stops. If it did not, every MiniCroft booted later in the
    same pytest process would load the skill in the last locale and route
    nothing. This test runs after every locale and reads that value."""
    assert SessionManager.get_default_session().lang == DEFAULT_LANG_AT_IMPORT
