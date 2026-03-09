import unittest

import os

from cache import Db
from tempfile import mkdtemp
from youtube import Client, CachingClient
import youtube_dl
import shutil

class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ytd = Client(youtube_dl.YoutubeDL(dict(verbose=True)))

    @classmethod
    def tearDownClass(cls):
        pass

    def test_get_video_data(self):
        data = TestClient.ytd.get_video_data('k23xhJoTbI4')
        self.assertIsNotNone(data)

    @unittest.skip('long running integration test')
    def test_get_channel_data(self):
        data = TestClient.ytd.get_channel_data('UCwYh0qBAF8HyKt0KUMp1rNg')
        self.assertIsNotNone(data)

    @unittest.skip('long running integration test')
    def test_get_playlist_data(self):
        data = TestClient.ytd.get_playlist_data('PL64wiCrrxh4KkVGYd3LebkmuGyIMUKzTz')
        self.assertIsNotNone(data)


class TestCachingClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current_dir = os.getcwd()
        cls.dirname = os.path.join(current_dir, '.cache', 'cachingclienttests')
        os.makedirs(TestCachingClient.dirname, exist_ok=True)
        cls.cache = Db(TestCachingClient.dirname, 'youtube').__enter__()
        cls.ytd = Client(youtube_dl.YoutubeDL(dict(verbose=True)))

    @classmethod
    def tearDownClass(cls):
        cls.cache.__exit__(None, None, None)
        shutil.rmtree(TestCachingClient.dirname)

    def setUp(self):
        self.caching_client = CachingClient(TestCachingClient.ytd, TestCachingClient.cache)

    def tearDown(self):
        self.caching_client = None

    def test_01_when_channel_is_not_cached_misses_increase(self):
        data = self.caching_client.get_channel_data('UCwYh0qBAF8HyKt0KUMp1rNg')
        self.assertIsNotNone(data)
        self.assertIsNotNone(data['name'])
        self.assertIsNotNone(data['videos'])
        self.assertIsNotNone(data['playlists'])
        self.assertIsNotNone(data['_raw'])
        stats = self.caching_client.stats()
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 1)

    def test_02_when_channel_is_cached_and_fetched_hits_increase(self):
        data = self.caching_client.get_channel_data('UCwYh0qBAF8HyKt0KUMp1rNg')
        self.assertIsNotNone(data)
        self.assertIsNotNone(data['name'])
        self.assertIsNotNone(data['videos'])
        self.assertIsNotNone(data['playlists'])
        self.assertIsNotNone(data['_raw'])
        stats = self.caching_client.stats()
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['hits'], 1)

    def test_03_when_video_is_cached_hits_increase(self):
        data = self.caching_client.get_video_data('-0YbKpVbZQM')
        self.assertIsNotNone(data)
        stats = self.caching_client.stats()
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['hits'], 2)

    def test_04_when_playlist_is_not_cached_misses_increase(self):
        data = self.caching_client.get_playlist_data('PLn0nrSd4xjjZsAaw5zUHxoRIiPtbQpwoB')
        self.assertIsNotNone(data)
        stats = self.caching_client.stats()
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['hits'], 2)

    def test_05_when_playlist_is_cached_hits_increase(self):
        data = self.caching_client.get_playlist_data('PLn0nrSd4xjjZsAaw5zUHxoRIiPtbQpwoB')
        self.assertIsNotNone(data)
        stats = self.caching_client.stats()
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['hits'], 3)

if __name__ == '__main__':
    unittest.main()
