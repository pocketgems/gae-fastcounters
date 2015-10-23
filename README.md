gae-fastcounters
=

gae-fastcounters is a library providing fast counters for the Python runtime on
Google App Engine.  It is extremely fast, lightweight (one file), and easy to
use.

Advantages:
-
 * __Lightweight__: One short file.
 * __Fast and Efficient__
     - [__Order of magnitude faster__](http://pocketgems.com/open-source-gae-fast-counters/)
       than sharding-based counter implementations
     - Uses memcache to minimize datastore interaction and update times
     - Uses the task queue to defer persistent updates until after the user's
       request is handled
     - Frequency of datastore writes is minimized by only writing at most once
       per user-defined update interval
     - Can fetch multiple counters en-masse
 * __Simple to Use__
     - Just three simple methods: `incr`, `get_count`, and `get_counts`


Limitations:
-

  * Counter values are limited to the range `[-2**63, 2**63 - 1]`
  * If the database update interval is not set to be immediate, then counters
    may *undercount* if an unpersisted portion of the count is evicted from
    memcache before it is persisted to the datastore.  By default, the update
    interval is 10 seconds.


Installation
-

After downloading and unpacking gae-fastcounters, copy the 'fastcounter.py' file
into your app's root directory.


Usage Notes
-

By default, changes will only be persisted to the datastore if a change to the
counter being updated hasn't been persisted in the last 10 seconds.  You can
modify this interval to suit your needs by passing an `update_interval`
parameter to `fastcounter.incr()`.

If you pass a very small `update_interval`, then all or nearly all changes will
trigger a task to be immediately enqueued to persist the change to the
datastore.  The smaller the interval, the smaller the chance that the counter
will lose a change.  However, updating them more frequently will use more
resources since every update will ultimately trigger a transactional database
write.  Also, beware contention - App Engine can only support so many updates
per second to any given entity, and fewer for transactional updates (it has
improved over time, but more than once per second is still pushing it; YMMY).


Example Usage
-

**Modifying Counters**

    import fastcounter
    # increment by one
    fastcounter.incr('my_counter0')

    # decrement by one
    fastcounter.incr('my_counter1', delta=-1)

    # persist this one more frequently
    fastcounter.incr('my_counter2', update_interval=5)


**Retrieving Counters**

    import fastcounter
    value0 = fastcounter.get_count('my_counter0')

    # if you ask for a counter which has never been used before, its value is 0
    value9 = fastcounter.get_count('my_counter9')

    # getting counters in bulk is far more efficient (every counter retrieval
    # call requires a round-trip to the datastore) values =
    values = fastcounter.get_counts(['my_counter%d' % i for i in xrange(100)])


_Author_: [Pocket Gems](http://www.pocketgems.com/)  
_Updated_: 2012-Feb-06 (v0.1)  
_License_: Apache License Version 2.0

If you discover a problem, please report it on the [gae-fastcounters issues page](https://github.com/pocketgems/gae-fastcounters/issues).
