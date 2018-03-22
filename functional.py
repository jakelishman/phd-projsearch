"""Functional programming utilities for working with generators."""

import itertools

def exists(predicate, iterable):
    """exists(predicate: 'T -> bool, iterable: iter of 'T) -> 'T

    Check whether any element of `iterable` matches `predicate`.  Functionally
    equivalent to `any(map(predicate, iterable))`."""
    for element in iterable:
        if predicate(element):
            return True
    return False

def skip(n, iterable):
    """skip(n: int > 0, iterable: iter of 'T) -> iter of 'T

    Skip the first `n` values from an iterator.  This just calls `next()` on the
    iterator to skip the values, so their side effects will still be evaluated
    and take time."""
    try:
        for _ in range(n):
            next(iterable)
        return iterable
    except StopIteration:
        return iter([])

def tuples(iterable, n=2):
    """tuples(iterable: iter of 'T, n: int > 0) -> iter of ('T)^n

    Produce an iterator which yields successive values of the iterator as
    overlapping n-tuples, for example
        tuples(range(3), 2) -> [ (0, 1), (1, 2) ]
    and so on."""
    return zip(*map(lambda t: skip(*t), enumerate(itertools.tee(iterable, n))))
