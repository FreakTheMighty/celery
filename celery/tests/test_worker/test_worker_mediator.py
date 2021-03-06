from celery.tests.utils import unittest

from Queue import Queue

from mock import Mock, patch

from celery.utils import gen_unique_id
from celery.worker.mediator import Mediator
from celery.worker.state import revoked as revoked_tasks


class MockTask(object):
    hostname = "harness.com"
    task_id = 1234
    task_name = "mocktask"

    def __init__(self, value, **kwargs):
        self.value = value

    on_ack = Mock()

    def revoked(self):
        if self.task_id in revoked_tasks:
            self.on_ack()
            return True
        return False


class test_Mediator(unittest.TestCase):

    def test_mediator_start__stop(self):
        ready_queue = Queue()
        m = Mediator(ready_queue, lambda t: t)
        m.start()
        self.assertFalse(m._shutdown.isSet())
        self.assertFalse(m._stopped.isSet())
        m.stop()
        m.join()
        self.assertTrue(m._shutdown.isSet())
        self.assertTrue(m._stopped.isSet())

    def test_mediator_move(self):
        ready_queue = Queue()
        got = {}

        def mycallback(value):
            got["value"] = value.value

        m = Mediator(ready_queue, mycallback)
        ready_queue.put(MockTask("George Costanza"))

        m.move()

        self.assertEqual(got["value"], "George Costanza")

    @patch("os._exit")
    def test_mediator_crash(self, _exit):
        ms = [None]

        class _Mediator(Mediator):

            def move(self):
                try:
                    raise KeyError("foo")
                finally:
                    ms[0]._shutdown.set()

        ready_queue = Queue()
        ms[0] = m = _Mediator(ready_queue, None)
        ready_queue.put(MockTask("George Constanza"))
        m.run()

        self.assertTrue(_exit.call_count)

    def test_mediator_move_exception(self):
        ready_queue = Queue()

        def mycallback(value):
            raise KeyError("foo")

        m = Mediator(ready_queue, mycallback)
        ready_queue.put(MockTask("Elaine M. Benes"))

        m.move()

    def test_run(self):
        ready_queue = Queue()

        condition = [None]

        def mycallback(value):
            condition[0].set()

        m = Mediator(ready_queue, mycallback)
        condition[0] = m._shutdown
        ready_queue.put(MockTask("Elaine M. Benes"))

        m.run()
        self.assertTrue(m._shutdown.isSet())
        self.assertTrue(m._stopped.isSet())

    def test_mediator_move_revoked(self):
        ready_queue = Queue()
        got = {}

        def mycallback(value):
            got["value"] = value.value

        m = Mediator(ready_queue, mycallback)
        t = MockTask("Jerry Seinfeld")
        t.task_id = gen_unique_id()
        revoked_tasks.add(t.task_id)
        ready_queue.put(t)

        m.move()

        self.assertNotIn("value", got)
        self.assertTrue(t.on_ack.call_count)
