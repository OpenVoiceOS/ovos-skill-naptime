"""`wake_word` must answer for every hotwords configuration, not just ours.

Two defects, both inherited on dev and both found by the live probe of #130
(`knowledge/wiki/audits/gate-ledger/live-ovos-skill-naptime-130.md`):

* `candidates` is a dict keyed by wake-word name, and the fallback returned
  `candidates[0]`. That asks for a key named 0, so a box whose
  `listener.wake_word` is not a hotwords key, while other hotwords still
  listen, raised KeyError and the skill spoke `skill.error`.
* the language preference compared `ww_conf.get("lang", "")` against
  `self.lang` exactly. Shipped entries carry `None` or a lowercase tag such
  as `"en-us"` against `"en-US"`, so the branch never matched and the
  preference was dead code.
"""
import unittest
from unittest.mock import patch

from ovos_utils.fakebus import FakeBus

from ovos_skill_naptime import NapTimeSkill

SKILL_ID = "ovos-skill-naptime.openvoiceos"


def _config(wake_word, hotwords):
    return {"listener": {"wake_word": wake_word}, "hotwords": hotwords}


class TestWakeWordSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill = NapTimeSkill()
        cls.skill._startup(FakeBus(), SKILL_ID)

    def _wake_word(self, config, lang="en-US"):
        with patch("ovos_skill_naptime.Configuration", return_value=config), \
                patch.object(type(self.skill), "lang", lang):
            return self.skill.wake_word

    def test_a_listener_wake_word_that_is_a_hotwords_key_wins(self):
        # The control for everything below: the early return still works and
        # the fallback is not reached.
        config = _config("hey_mycroft", {
            "hey_mycroft": {"listen": True, "lang": "en-US"},
            "hey_jarvis": {"listen": True, "lang": "en-US"},
        })
        self.assertEqual(self._wake_word(config), "hey_mycroft")

    def test_a_listener_wake_word_absent_from_hotwords_falls_back(self):
        # The KeyError case: `listener.wake_word` names something hotwords
        # does not define, and other hotwords listen.
        config = _config("computer", {
            "hey_jarvis": {"listen": True, "lang": "de-DE"},
            "hey_mycroft": {"listen": True, "lang": "de-DE"},
        })
        self.assertEqual(self._wake_word(config), "hey_jarvis")

    def test_the_fallback_keeps_config_order(self):
        config = _config("computer", {
            "second": {"listen": True, "lang": "de-DE"},
            "first": {"listen": True, "lang": "de-DE"},
        })
        self.assertEqual(self._wake_word(config), "second")

    def test_a_lowercase_language_tag_still_matches(self):
        # "en-us" against self.lang "en-US".
        config = _config("computer", {
            "german_one": {"listen": True, "lang": "de-DE"},
            "english_one": {"listen": True, "lang": "en-us"},
        })
        self.assertEqual(self._wake_word(config), "english_one")

    def test_a_null_language_does_not_raise(self):
        # `standardize_lang(None)` raises AttributeError, so a shipped entry
        # carrying `lang: null` must not reach it.
        config = _config("computer", {
            "no_lang": {"listen": True, "lang": None},
            "english_one": {"listen": True, "lang": "en-US"},
        })
        self.assertEqual(self._wake_word(config), "english_one")

    def test_a_hotword_that_does_not_listen_is_not_a_candidate(self):
        config = _config("computer", {
            "not_listening": {"listen": False, "lang": "en-US"},
            "listening": {"listen": True, "lang": "de-DE"},
        })
        self.assertEqual(self._wake_word(config), "listening")

    def test_no_listening_hotword_returns_the_configured_default(self):
        config = _config("computer", {
            "not_listening": {"listen": False, "lang": "en-US"},
        })
        self.assertEqual(self._wake_word(config), "computer")


if __name__ == "__main__":
    unittest.main()
