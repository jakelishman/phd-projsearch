import itertools

def exists(predicate, iterable):
    for element in iterable:
        if predicate(element):
            return True
    return False

def skip(n, iterable):
    try:
        for _ in range(n):
            next(iterable)
        return iterable
    except StopIteration:
        return iter([])

def tuples(iterable, n=2):
    return zip(*map(lambda t: skip(*t), enumerate(itertools.tee(iterable, n))))
