"""Regression tests for the listener-lifecycle bus topics.

Covers both directions of the ovos_spec_tools.SpecMessage migration: the
sleep intent must put the canonical ``ovos.listener.sleep`` topic on the
wire, and the wake-up handler must fire exactly once whether the awoken
signal arrives spelled as the legacy ``mycroft.awoken`` or the spec
``ovos.listener.awoken`` (the bus-client namespace bridge dedupes a handler
registered on one spelling against a twin on the wire in the other).
"""
import unittest
from unittest.mock import patch

from ovos_bus_client.message import Message
from ovos_spec_tools import SpecMessage
from ovos_utils.messagebus import FakeBus

from ovos_skill_naptime import NapTimeSkill

SKILL_ID = "ovos-skill-naptime.openvoiceos"


class TestListenerLifecycleTopics(unittest.TestCase):
    def _make_skill(self):
        bus = FakeBus()
        skill = NapTimeSkill()
        skill._startup(bus, SKILL_ID)
        return skill, bus

    def test_sleep_emits_spec_listener_sleep_topic(self):
        skill, bus = self._make_skill()
        seen = []
        bus.on("message", lambda m: seen.append(Message.deserialize(m).msg_type))
        skill.handle_go_to_sleep(Message("naptime.intent"))
        self.assertIn(SpecMessage.LISTENER_SLEEP, seen)

    def test_awoken_fires_once_on_spec_topic(self):
        skill, bus = self._make_skill()
        skill.started_by_skill = True
        with patch.object(skill, "awaken", wraps=skill.awaken) as awaken_mock:
            bus.emit(Message(SpecMessage.LISTENER_AWOKEN))
            self.assertEqual(awaken_mock.call_count, 1)

    def test_awoken_fires_once_on_legacy_topic(self):
        skill, bus = self._make_skill()
        skill.started_by_skill = True
        with patch.object(skill, "awaken", wraps=skill.awaken) as awaken_mock:
            bus.emit(Message("mycroft.awoken"))
            self.assertEqual(awaken_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
