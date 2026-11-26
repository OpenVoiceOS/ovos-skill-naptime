"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the expected intent handler.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-naptime.openvoiceos"
LANG = "en-US"

# the go-to-sleep handler and its enclosure/animation events emit a number of
# side-effect bus messages (mark1 eyes, recognizer_loop:sleep, context/config
# patches). These are not part of intent routing and are ignored so the capture
# stream carries the canonical handler skeleton.
_SIDE_EFFECT_MESSAGES = [
    "mycroft.audio.play_sound",
    "mycroft.awoken",
    "ovos.listener.awoken",
    "recognizer_loop:sleep",
    "ovos.listener.sleep",
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

NAPTIME = f"{SKILL_ID}:naptime"


class TestNaptimeIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _session(self, session_id):
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        session.blacklisted_intents = []
        return session

    def _utterance(self, text, session):
        return Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )

    def _run(self, text, session_id="test-session"):
        session = self._session(session_id)
        capture = CaptureSession(
            self.minicroft, ignore_messages=_SIDE_EFFECT_MESSAGES
        )
        capture.capture(self._utterance(text, session), timeout=30)
        return [m.msg_type for m in capture.finish()]

    def test_go_to_sleep(self):
        TALLY.assert_routed("go to sleep", NAPTIME, self._run("go to sleep"))

    def test_nap_time(self):
        TALLY.assert_routed("nap time", NAPTIME, self._run("nap time"))

    def test_enter_sleep_mode(self):
        TALLY.assert_routed("enter sleep mode", NAPTIME, self._run("enter sleep mode"))


if __name__ == "__main__":
    unittest.main()
