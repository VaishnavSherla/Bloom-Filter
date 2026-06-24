import pickle

from BloomFilter import BloomFilter


class ScalableBloomFilter:
    """
    A chain of standard BloomFilter instances that grows over time instead
    of being sized once and left to saturate.

    Why this exists
    ----------------
    A single BloomFilter is sized for an expected `n`. If you insert far more
    elements than planned, the bit array saturates silently — false positive
    rate climbs and the filter degrades without ever raising an error.

    You can't resize a bitarray in place without rehashing every element
    that's already in it (the array IS the data — there's no element list to
    replay). So instead of resizing, this class detects saturation via
    fill_ratio() and appends a brand new filter to a chain:

      - All inserts go to the newest (active) filter only.
      - A lookup checks every filter in the chain; if ANY filter says yes,
        the overall answer is "probably present".
      - When the active filter's fill ratio crosses `growth_threshold`,
        a new filter is appended and becomes the new active filter.

    This is the standard "Scalable Bloom Filter" pattern — same idea Redis
    Bloom and other production libraries use to avoid a single saturating
    filter.
    """

    def __init__(self, initial_capacity, false_positive_rate=0.01, growth_threshold=0.5, growth_factor=2):
        """
        initial_capacity : expected number of elements for the FIRST filter
        false_positive_rate : target FPR for each individual filter in the chain
        growth_threshold : fill ratio (0-1) at which we stop inserting into
                            the current filter and create a new one
        growth_factor : each new filter is sized for growth_factor times as
                         many elements as the previous one, since systems
                         that outgrow their original estimate tend to keep
                         growing, not plateau
        """
        self.false_positive_rate = false_positive_rate
        self.growth_threshold = growth_threshold
        self.growth_factor = growth_factor
        self.filters = []
        self._add_new_filter(initial_capacity)

    def _add_new_filter(self, capacity):
        num_bits, num_hash_functions = BloomFilter.optimal_parameters(capacity, self.false_positive_rate)
        self.filters.append(BloomFilter(num_hash_functions, num_bits))

    def _active_filter(self):
        return self.filters[-1]

    def add(self, item):
        active = self._active_filter()

        # If the active filter is already saturated past the threshold,
        # grow the chain BEFORE inserting, so this element lands in fresh
        # capacity rather than pushing an already-strained filter further.
        if active.fill_ratio() >= self.growth_threshold:
            next_capacity = max(active.num_inserted, 1) * self.growth_factor
            self._add_new_filter(next_capacity)
            active = self._active_filter()

        active.add(item)

    def contains(self, item):
        # Check every filter in the chain. A single "no" anywhere does NOT
        # mean the item is absent overall — it might be present in another
        # filter in the chain. Only if ALL filters say "no" can we guarantee
        # the item was never inserted.
        return any(f.contains(item) for f in self.filters)

    def build(self, file):
        try:
            with open(file, 'r') as f:
                for line in f:
                    self.add(line.strip().lower())
        except FileNotFoundError:
            print(f"File {file} not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def total_inserted(self):
        return sum(f.num_inserted for f in self.filters)

    def stats(self):
        """Per-filter breakdown plus chain-level totals. This is what you'd
        wire up to a metrics dashboard in production — fill_ratio per shard
        of the chain tells you exactly when growth events happened."""
        per_filter = [f.stats() for f in self.filters]
        total_bits = sum(f["num_bits"] for f in per_filter)
        total_inserted = self.total_inserted()
        return {
            "num_filters": len(self.filters),
            "total_bits": total_bits,
            "total_inserted": total_inserted,
            "growth_threshold": self.growth_threshold,
            "filters": per_filter,
        }

    def save(self, filename):
        try:
            with open(filename, 'wb') as f:
                pickle.dump(
                    {
                        "false_positive_rate": self.false_positive_rate,
                        "growth_threshold": self.growth_threshold,
                        "growth_factor": self.growth_factor,
                        "filter_blobs": [
                            (f.num_hash_functions, f.num_bits, f.get_bytes(), f.num_inserted)
                            for f in self.filters
                        ],
                    },
                    f,
                )
        except Exception as e:
            print(f"An error occurred while saving the file: {e}")

    @classmethod
    def load_from_file(cls, filename):
        with open(filename, 'rb') as f:
            data = pickle.load(f)

        instance = cls.__new__(cls)
        instance.false_positive_rate = data["false_positive_rate"]
        instance.growth_threshold = data["growth_threshold"]
        instance.growth_factor = data["growth_factor"]
        instance.filters = [
            BloomFilter(num_hash_functions, num_bits, filter_data, num_inserted)
            for num_hash_functions, num_bits, filter_data, num_inserted in data["filter_blobs"]
        ]
        return instance
