"""Functional programming utilities for working with generators."""

import itertools
import functools

__all__ = ['exists', 'skip', 'tuples', 'flat_map', 'funnel_map', 'compose']

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

def flat_map(mapping, iterable):
    """flatmap(mapping: 'A -> iterable of 'B, iterable: iterable of 'A)
    -> iterable of 'B

    Applies `mapping` to each element of `iterable`, flattening out returned
    iterators."""
    for el in iterable:
        yield from mapping(el)

class funnel_map:
    """funnelmap(consumer: iterator of 'A -> 'B, iterable: iterable of 'A)
    -> iterable of 'B

    Creates a new iterable using the `consumer` function on the given
    `iterable`.  The consumer function may consume as many values as it likes
    from the base iterable, and then return a value.  For each subsequent value,
    the underlying iterable continues from the place it was left off at.

    The `consumer` function may raise `StopIteration` which will terminate the
    iteration even if the iterator itself is not exhausted."""
    def __init__(self, consumer, iterable):
        self._consumer = consumer
        self._iterator = iter(iterable)
    def __next__(self):
        return self._consumer(self._iterator)
    def __iter__(self):
        return self

def _compose(funcs, x):
    for f in funcs:
        x = f(x)
    return x

def compose(first_function, *more_functions, left=False):
    """compose(first_function: 'A -> 'B, *more_functions: 'B -> 'C) -> 'A -> 'C
    compose(functions_iter) -> 'A -> 'Z

    Return the composition of the functions given.  This can be either
    right-composition (the default), e.g.
        compose(f, g)(x) == g(f(x))
    which is more useful for list reductions or left-composition (by using the
    keyword argument `left=True`), e.g.
        compose(f, g)(x) == f(g(x))
    which looks more like mathematical notation.

    If the first argument is an iterator, then compose will return the relevant
    composition of all the functions in the iterator."""
    try:
        functions = tuple(first_function)
    except TypeError:
        functions = first_function, *more_functions
    if left:
        functions = reversed(functions)
    return functools.partial(_compose, functions)
