"""Which topologies make up a density sweep at a fixed number of routers."""
from functools import partial

from . import families as F

FAMILIES = ("random-regular", "leaf-spine", "flattened-butterfly")


def degree_steps(low, high):
    """3, 4, 6, 8, 12, 16, 24, 32, 48, ... between low and high, and high itself."""
    steps = {2 ** i for i in range(1, 32)} | {3 * 2 ** i for i in range(31)}
    return sorted({x for x in steps if low <= x <= high} | {high})


def factorizations(n, largest=None):
    """Every way to write n as a product of factors of at least 2, each list largest first."""
    if n == 1:
        return [()]
    largest = n if largest is None else largest
    out = []
    for f in range(min(n, largest), 1, -1):
        if n % f == 0:
            out += [(f,) + rest for rest in factorizations(n // f, f)]
    return out


def plan(routers, families=FAMILIES, seeds=(1,)):
    """(file name, builder) for every topology of the sweep, each family from sparsest to densest.

    random-regular: degree 3, 4, 6, 8, 12, ... up to routers - 1 (the full mesh); with an odd number of routers only
    even degrees exist.  leaf-spine: 2, 3, 4, 6, 8, 12, ... spines up to half the routers, the rest leaves.
    flattened-butterfly: every factorization of the number of routers; a prime number has only the full mesh."""
    n = routers
    if n < 4:
        raise ValueError("a sweep needs at least 4 routers")
    unknown = set(families) - set(FAMILIES)
    if unknown:
        raise ValueError(f"unknown families {sorted(unknown)}; choose from {list(FAMILIES)}")
    jobs = []
    if "random-regular" in families:
        for d in degree_steps(3, n - 1):
            if n * d % 2 == 0:
                jobs += [(f"random-regular-n{n}-d{d}-s{s}.json", partial(F.random_regular, n, d, s)) for s in seeds]
    if "leaf-spine" in families:
        for sp in degree_steps(2, n // 2):
            jobs.append((f"leaf-spine-n{n}-spines{sp}.json", partial(F.leaf_spine, n - sp, sp)))
    if "flattened-butterfly" in families:
        for r in sorted(factorizations(n), key=lambda r: (sum(k - 1 for k in r), r)):
            name = "x".join(map(str, r))
            jobs.append((f"flattened-butterfly-n{n}-k{name}.json", partial(F.flattened_butterfly, r)))
    return jobs
