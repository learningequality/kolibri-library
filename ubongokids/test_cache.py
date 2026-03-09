import unittest

from cache import Db
from tempfile import mkdtemp


class TestCacheDbMethods(unittest.TestCase):
    def setUp(self):
        dirname = mkdtemp(suffix='caching', prefix='teststorage')
        self.cache = Db(dirname, 'rawcaching').__enter__()

    def tearDown(self):
        self.cache.__exit__(None, None, None)

    def test_add_found(self):
        self.cache.add(key='hola', data=u'mundo!')
        found, data = self.cache.get('hola')
        assert found
        assert data == 'mundo!'
        stats = self.cache.stats()
        assert stats['misses'] == 0
        assert stats['hits'] == 1

    def test_add_not_found(self):
        found, data = self.cache.get('hola')
        assert not found
        assert not data
        stats = self.cache.stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 0

    def test_remove(self):
        self.cache.add(key='hola', data=u'mundo!')
        self.cache.remove('hola')
        found, data = self.cache.get('hola')
        assert not found
        assert not data

    def test_change(self):
        self.cache.add(key='hola', data=u'mundo!')
        found, data = self.cache.get('hola')
        assert found
        assert data == 'mundo!'
        self.cache.add(key='hola', data=u'world!')
        found, data = self.cache.get('hola')
        assert found
        assert data == 'world!'

    def test_hits_and_misses(self):
        members = 10
        times = 5

        # Exercise the cache
        for i in range(0, members * times):
            found, data = self.cache.get(str(i % members))
            if not found:
                key = str(i)
                self.cache.add(key=key, data='value_{}'.format(key))

        stats = self.cache.stats()
        assert stats['misses'] == members
        assert stats['hits'] == (members * times) - members

if __name__ == '__main__':
    unittest.main()
