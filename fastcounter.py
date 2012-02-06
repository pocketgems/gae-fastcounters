"""Fast counter library for App Engine.

Counter increments generally only touch memcache, and occasionally enqueue a
task.  Both are very fast and low overhead.  The downside is that the counter
could undercount (e.g., if memcache data is evicted before it is persisted via
a task).  The task which increments the datastore-based counter is not
idempotent and would double-count if ran extra time(s).  However, this should
be rather exceptional based on App Engine's documentation.
"""
import logging
import random

from google.appengine.api import memcache
from google.appengine.api.taskqueue import taskqueue
from google.appengine.ext import db, webapp

__all__ = ['get_count', 'get_counts', 'incr']


class Counter(db.Model):
    """Persistent storage of a counter's values"""
    # key_name is the counter's name
    value = db.IntegerProperty(indexed=False)


def get_count(name):
    """Returns the count of the specified counter name.

    If it doesn't exist, 0 is returned.  For counters which do exist, the
    returned count includes both the persisted (datastore) count plus the
    unpersisted memcache count.  It does not include any count waiting to be
    persisted on the task queue.
    """
    c = Counter.get_by_key_name(name)
    fmc = int(memcache.get("ctr_val:" + name) or BASE_VALUE) - BASE_VALUE
    if c:
        return c.value + fmc
    else:
        return fmc


def get_counts(names):
    """Like get_count, but fetches multiple counts at once which is much
    more efficient than getting them one at a time.
    """
    db_keys = [db.Key.from_path('Counter', name) for name in names]
    db_counts = db.get(db_keys)
    mc_counts = memcache.get_multi(names, 'ctr_val:')
    ret = []
    for i, name in enumerate(names):
        db_count = (db_counts[i] and db_counts[i].value) or 0
        mc_count = int(mc_counts.get(name, BASE_VALUE)) - BASE_VALUE
        ret.append(db_count + mc_count)
    return ret

# Memcache incr/decr only works on 64-bit *unsigned* integers, and it
# does not underflow.  By starting the memcache count at half of the
# maximum value, we can still allow both positive and negative deltas.
BASE_VALUE = 2 ** 63


def incr(name, delta=1, update_interval=10):
    """Increments a counter.  The increment is generally a memcache-only
    operation, though a task will also be enqueued about once per
    update_interval.  May under-count if memcache contents is lost.

    Args:
      name: The name of the counter.
      delta: Amount to increment counter by, defaulting to 1.
      update_interval: Approximate interval, in seconds, between updates.  Must
                       be greater than zero.
    """
    lock_key = "ctr_lck:" + name
    delta_key = "ctr_val:" + name

    # update memcache
    if delta >= 0:
        v = memcache.incr(delta_key, delta, initial_value=BASE_VALUE)
    elif delta < 0:
        v = memcache.decr(delta_key, -delta, initial_value=BASE_VALUE)

    if memcache.add(lock_key, None, time=update_interval):
        # time to enqueue a new task to persist the counter
        # note: cast to int on next line is due to GAE issue 2012
        # (http://code.google.com/p/googleappengine/issues/detail?id=2012)
        v = int(v)
        delta_to_persist = v - BASE_VALUE
        if delta_to_persist == 0:
            return  # nothing to save

        try:
            qn = random.randint(0, 4)
            qname = 'PersistCounter%d' % qn
            taskqueue.add(url='/task/counter_persist_incr',
                          queue_name=qname,
                          params=dict(name=name,
                                      delta=delta_to_persist))
        except:
            # task queue failed but we already put the delta in memcache;
            # just try to enqueue the task again next interval
            return

        # we added the task --> need to decr memcache so we don't double-count
        failed = False
        if delta_to_persist > 0:
            if memcache.decr(delta_key, delta=delta_to_persist) is None:
                failed = True
        elif delta_to_persist < 0:
            if memcache.incr(delta_key, delta=-delta_to_persist) is None:
                failed = True
        if failed:
            logging.warn("counter %s reset failed (will double-count): %d",
                         name, delta_to_persist)


class CounterPersistIncr(webapp.RequestHandler):
    """Task handler for incrementing the datastore's counter value."""
    def post(self):
        name = self.request.get('name')
        delta = int(self.request.get('delta'))
        db.run_in_transaction(CounterPersistIncr.incr_counter, name, delta)

    @staticmethod
    def incr_counter(name, delta):
        c = Counter.get_by_key_name(name)
        if not c:
            c = Counter(key_name=name, value=delta)
        else:
            c.value += delta
        c.put()
