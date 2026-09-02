# write your first unittest!
import unittest
from os.path import join, dirname
import os
from ovos_utils.bracket_expansion import expand_parentheses, expand_options


def read_samples(path):
    samples = []
    with open(path) as fi:
        for _ in fi.read().split("\n"):
            if _ and not _.strip().startswith("#"):
                samples += expand_options(_)
    return samples


class TestPadaos(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        from padaos import IntentContainer
        res_folder = join(dirname(dirname(dirname(__file__))), "locale", "en-us")
        engine = IntentContainer()
        for root, folders, files in os.walk(res_folder):
            for f in files:
                samples = read_samples(join(root, f))
                if f.endswith(".intent"):
                    engine.add_intent(f.replace(".intent", ""), samples)
                if f.endswith(".entity"):
                    engine.add_entity(f.replace(".entity", ""), samples)
        self.engine = engine
        self.res_folder = res_folder

    def test_padaos(self):
        for root, folders, files in os.walk(self.res_folder):
            for f in files:
                if f.endswith(".intent"):
                    samples = read_samples(join(root, f))
                    for s in samples:
                        self.assertEqual(self.engine.calc_intent(s),
                                         {'entities': {}, 'name': f.replace(".intent", "")})



class TestPadatious(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        from padatious import IntentContainer
        res_folder = join(dirname(dirname(dirname(__file__))), "locale", "en-us")
        engine = IntentContainer(cache_dir="/tmp/padatious_cache")
        for root, folders, files in os.walk(res_folder):
            for f in files:
                samples = read_samples(join(root, f))
                if f.endswith(".intent"):
                    engine.add_intent(f.replace(".intent", ""), samples)
                if f.endswith(".entity"):
                    engine.add_entity(f.replace(".entity", ""), samples)
        engine.train(force=True)
        self.engine = engine
        self.res_folder = res_folder

    def test_padatious(self):
        for root, folders, files in os.walk(self.res_folder):
            for f in files:
                if f.endswith(".intent"):
                    samples = read_samples(join(root, f))
                    for s in samples:
                        self.assertEqual(self.engine.calc_intent(s).name,
                                         f.replace(".intent", ""))


class TestPadacioso(unittest.TestCase):
    """The production pipeline (ovos-padacioso-pipeline-plugin) registers
    ``.intent`` files as raw lines and expands them via
    ``ovos_spec_tools.expand``, which understands ``[optional]`` segments --
    unlike the legacy ``expand_options`` helper used by ``TestPadaos``/
    ``TestPadatious`` above. This exercises the same engine and expansion the
    skill sees at runtime.
    """
    @classmethod
    def setUpClass(cls):
        from padacioso import IntentContainer
        res_folder = join(dirname(dirname(dirname(__file__))), "locale", "en-US")
        engine = IntentContainer()
        for root, folders, files in os.walk(res_folder):
            for f in files:
                path = join(root, f)
                with open(path) as fi:
                    lines = [l for l in fi.read().split("\n")
                             if l and not l.strip().startswith("#")]
                if f.endswith(".intent"):
                    engine.add_intent(f.replace(".intent", ""), lines)
                if f.endswith(".entity"):
                    engine.add_entity(f.replace(".entity", ""), lines)
        cls.engine = engine

    def test_new_naptime_lines_match(self):
        for utterance in ("time to nap",
                           "nap time",
                           "nap time for the baby",
                           "nap time for the kids",
                           "nap time for the kid",
                           "go to sleep now",
                           "go to sleep now honey",
                           "go to sleep now sweetie",
                           "it's nap time"):
            match = self.engine.calc_intent(utterance)
            self.assertEqual(match.get("name"), "naptime", utterance)

    def test_wake_words_not_claimed(self):
        for utterance in ("wake", "wake up"):
            match = self.engine.calc_intent(utterance)
            self.assertIsNone(match.get("name"), utterance)

