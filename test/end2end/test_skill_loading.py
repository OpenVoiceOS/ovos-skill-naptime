import unittest

from ovos_plugin_manager.skills import find_skill_plugins
from ovos_utils.messagebus import FakeBus

from skill_ovos_naptime import NapTimeSkill


class TestSkillLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_id = "ovos-skill-naptime.openvoiceos"

    def test_find_plugin(self):
        plugins = find_skill_plugins()
        self.assertIn(self.skill_id, list(plugins))

    def test_from_class(self):
        bus = FakeBus()
        skill = NapTimeSkill()
        skill._startup(bus, self.skill_id)
        self.assertEqual(skill.bus, bus)
        self.assertEqual(skill.skill_id, self.skill_id)
