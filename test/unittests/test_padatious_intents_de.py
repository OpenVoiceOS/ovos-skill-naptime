# write your first unittest!
import unittest
from os.path import join, dirname
import os
import tempfile
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
        res_folder = join(dirname(dirname(dirname(__file__))), "locale", "de-DE")
        engine = IntentContainer()
        for root, folders, files in os.walk(res_folder):
            for f in files:
                samples = read_samples(join(root, f))
                if f.endswith(".intent"):
                    engine.add_intent(f.replace(".intent", ""), samples)
                if f.endswith(".entity"):
                    engine.add_entity(f.replace(".entity", ""), samples)
        # padaos compiles in a background worker, and calc_intents never
        # compiles on the match path: an uncompiled container answers None
        # for every query. Compile here, or the loop below asserts against
        # an empty regex table and passes whatever the locale holds.
        engine.compile()
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
        res_folder = join(dirname(dirname(dirname(__file__))), "locale", "de-DE")
        # A per-class temporary directory, not a fixed /tmp path. All six
        # locale files named the same one, and every locale writes the same
        # naptime.* cache keys into it, so the last locale to train won and
        # stale state survived between runs as well as between locales.
        cache = tempfile.TemporaryDirectory(prefix="naptime-padatious-")
        self.addClassCleanup(cache.cleanup)
        engine = IntentContainer(cache_dir=cache.name)
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

