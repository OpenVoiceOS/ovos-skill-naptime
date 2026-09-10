"""Effect assertions for ovos-skill-naptime's sleep/wake path.

``test_intents_en_us.py`` and the golden suite only assert that an utterance
routes to the naptime handler -- that passes for a handler that routes and
then raises, emits nothing, or emits the wrong bus message. The listener
sleep/wake path has a real bus effect (``ovos.listener.sleep`` /
``recognizer_loop:wake_up``) and a spoken confirmation whose text is loaded
here directly from the skill's own en-US dialog files, never from running the
handler and recording what came out.
"""
import re
import unittest
from pathlib import Path

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools import SpecMessage
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"
LANG = "en-US"
LOCALE_DIR = Path(__file__).parent.parent.parent / "locale" / "en-US"

_PIPELINE = [
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-low",
]


def _dialog_templates(name):
    """Read a .dialog file the same way ovos-workshop's dialog renderer does:
    one candidate sentence per non-empty line."""
    text = (LOCALE_DIR / name).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _collapse_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _template_matches(template, spoken):
    """A template may carry a ``{wake_word}`` placeholder; match the spoken
    text against the literal parts on either side of it (whitespace
    collapsed, since the renderer is not required to preserve a dialog
    source file's exact spacing)."""
    spoken = _collapse_ws(spoken)
    if "{wake_word}" not in template:
        return _collapse_ws(template) == spoken
    before, after = template.split("{wake_word}", 1)
    before, after = _collapse_ws(before), _collapse_ws(after)
    return spoken.startswith(before) and spoken.endswith(after)


class TestNaptimeEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _session(self, session_id):
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(_PIPELINE)
        session.blacklisted_intents = []
        return session

    def _utterance(self, text, session):
        return Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )

    def _fire(self, text, session):
        capture = CaptureSession(self.minicroft, ignore_messages=[])
        capture.capture(self._utterance(text, session), timeout=30)
        return capture.finish()

    @staticmethod
    def _updated_session(messages, fallback):
        # server-side context (eg. skill set_context) lives only on the
        # SessionManager copy; forward the session the server last handed
        # back, not a stale local snapshot, or the sleeping_state context
        # required by WakeUp.intent never survives to the next utterance.
        for m in reversed(messages):
            if m.msg_type == "ovos.utterance.handled":
                raw = m.context.get("session")
                if raw:
                    return Session.deserialize(raw)
        return fallback

    def test_go_to_sleep_emits_listener_sleep_and_confirmation(self):
        """The old suite asserted only that 'go to sleep' routed to the
        naptime intent handler. That is satisfied by a handler that routes,
        speaks nothing, and never puts the listener to sleep. Assert the
        actual bus effect: the listener-sleep message by type, and a spoken
        confirmation whose text is one of the skill's own going.to.sleep
        dialog renderings with the wake word substituted in."""
        session = self._session("effects-go-to-sleep")
        messages = self._fire("go to sleep", session)

        sleep_msgs = [m for m in messages if m.msg_type == SpecMessage.LISTENER_SLEEP]
        self.assertEqual(
            len(sleep_msgs), 1,
            f"expected exactly one {SpecMessage.LISTENER_SLEEP} message, got {messages!r}",
        )

        speak_msgs = [m for m in messages if m.msg_type == SpecMessage.SPEAK]
        self.assertGreaterEqual(
            len(speak_msgs), 1,
            f"expected a spoken confirmation, got types {[m.msg_type for m in messages]!r}",
        )

        spoken = speak_msgs[0].data["utterance"]
        # accept either the wake-word variant (any wake word string) or the
        # short fallback: the assertion is on the FIELD (data["utterance"])
        # carrying rendered dialog text, not on presence of a message.
        going_to_sleep_templates = _dialog_templates("going.to.sleep.dialog")
        going_to_sleep_short_templates = _dialog_templates("going.to.sleep.short.dialog")
        matches_long_form = any(_template_matches(t, spoken) for t in going_to_sleep_templates)
        matches_short_form = any(_template_matches(t, spoken) for t in going_to_sleep_short_templates)
        self.assertTrue(
            matches_long_form or matches_short_form,
            f"spoken confirmation {spoken!r} does not match any going.to.sleep(.short) dialog template",
        )

    def test_wake_up_after_sleep_forwards_wake_message(self):
        """The old suite never fired 'wake up' at all. The real effect of
        the wake-up path is telling ovos-listener to wake up over the bus;
        assert that message, by type, is actually forwarded -- not merely
        that some handler ran."""
        session = self._session("effects-wake-up")
        sleep_messages = self._fire("go to sleep", session)
        session = self._updated_session(sleep_messages, session)
        messages = self._fire("wake up", session)

        wake_msgs = [m for m in messages if m.msg_type == "recognizer_loop:wake_up"]
        self.assertEqual(
            len(wake_msgs), 1,
            f"expected exactly one recognizer_loop:wake_up message, got {[m.msg_type for m in messages]!r}",
        )


if __name__ == "__main__":
    unittest.main()
