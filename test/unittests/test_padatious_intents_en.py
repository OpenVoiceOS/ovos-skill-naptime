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
        from ovos_padatious.padaos import IntentContainer
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
        from ovos_padatious import IntentContainer
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

    def test_wake_phrases_belong_to_wake_up(self):
        # These phrases DO match wake_up at the engine level, and must: they
        # are wake_up.intent's own lines. What stops naptime answering "wake"
        # while the device is awake is not the engine, it is the gate --
        # handle_wakeup declares requires_context=["sleeping_state"], set only
        # by handle_sleep. A bare padacioso container built from the locale
        # files cannot model that gate, so asserting "no intent claims these"
        # here asserts something false about the engine.
        #
        # The real behaviour is covered on a booted MiniCroft in
        # test/end2end/test_wakeup_context_gate.py, which checks both arms in
        # two pipelines: "wake up" in a fresh session must NOT match wake_up,
        # and must match after "go to sleep".
        #
        # This row is kept as a locale guard: if the lines ever leave
        # wake_up.intent, the context-gated handler becomes unreachable.
        for utterance in ("wake", "wake up"):
            match = self.engine.calc_intent(utterance)
            self.assertEqual(match.get("name"), "wake_up", utterance)

