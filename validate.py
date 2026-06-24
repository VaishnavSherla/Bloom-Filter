"""
validate.py — empirical correctness + benchmark checks for the Bloom filter.

Two things this answers, both of which are the natural follow-up questions
to "I built a Bloom filter":

1. "Does the false-positive rate actually match the formula?"
   -> measure_false_positive_rate() inserts a known word list, then tests a
      disjoint set of words NOT in that list, and reports what fraction come
      back as false positives. Compared directly against the theoretical
      estimate from BloomFilter.estimated_false_positive_rate().

2. "Why use this over a plain Python set?"
   -> benchmark_vs_set() compares memory footprint (via sys.getsizeof plus
      the actual bytes of the underlying structures) and lookup speed for
      the same word list, so the trade-off has real numbers instead of
      a hand-wave.
"""

import random
import string
import sys
import time

from BloomFilter import BloomFilter


def _load_words(path, limit=None):
    with open(path, 'r') as f:
        words = [line.strip().lower() for line in f if line.strip()]
    return words[:limit] if limit else words


def _random_word(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def measure_false_positive_rate(word_file, false_positive_rate=0.01, num_trials=100_000, limit=None):
    """
    Builds a fresh filter from word_file, then probes it with num_trials
    randomly generated strings that are (with overwhelming probability) NOT
    in the source word list. Reports the actual observed FPR vs the
    theoretical estimate the filter itself computes from its current fill
    ratio.
    """
    real_words = _load_words(word_file, limit=limit)
    real_word_set = set(real_words)  # for filtering out accidental collisions in our random probes

    num_bits, num_hash_functions = BloomFilter.optimal_parameters(len(real_words), false_positive_rate)
    bf = BloomFilter(num_hash_functions, num_bits)
    for w in real_words:
        bf.add(w)

    false_positives = 0
    valid_trials = 0
    attempts = 0
    while valid_trials < num_trials and attempts < num_trials * 2:
        attempts += 1
        candidate = _random_word(length=random.randint(5, 12))
        if candidate in real_word_set:
            continue  # this isn't a "negative" probe if it's actually a real word
        valid_trials += 1
        if bf.contains(candidate):
            false_positives += 1

    observed_fpr = false_positives / valid_trials if valid_trials else 0.0
    theoretical_fpr = bf.estimated_false_positive_rate()

    return {
        "words_inserted": len(real_words),
        "target_fpr": false_positive_rate,
        "trials": valid_trials,
        "false_positives": false_positives,
        "observed_fpr": observed_fpr,
        "theoretical_fpr": theoretical_fpr,
        "num_bits": num_bits,
        "num_hash_functions": num_hash_functions,
    }


def benchmark_vs_set(word_file, false_positive_rate=0.01, limit=None, lookup_trials=50_000):
    """
    Same word list, two structures: BloomFilter vs Python set.
    Compares memory footprint and average lookup latency.
    """
    words = _load_words(word_file, limit=limit)

    # --- Bloom filter ---
    num_bits, num_hash_functions = BloomFilter.optimal_parameters(len(words), false_positive_rate)
    bf = BloomFilter(num_hash_functions, num_bits)
    t0 = time.perf_counter()
    for w in words:
        bf.add(w)
    bf_build_time = time.perf_counter() - t0
    bf_memory_bytes = len(bf.get_bytes())

    # --- Python set ---
    t0 = time.perf_counter()
    py_set = set(words)
    set_build_time = time.perf_counter() - t0
    set_memory_bytes = sys.getsizeof(py_set) + sum(sys.getsizeof(w) for w in py_set)

    # --- Lookup speed: same probe words for both structures ---
    probes = [random.choice(words) for _ in range(lookup_trials // 2)] + \
             [_random_word(length=9) for _ in range(lookup_trials // 2)]

    t0 = time.perf_counter()
    for p in probes:
        bf.contains(p)
    bf_lookup_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for p in probes:
        _ = p in py_set
    set_lookup_time = time.perf_counter() - t0

    return {
        "num_words": len(words),
        "bloom_filter": {
            "memory_bytes": bf_memory_bytes,
            "memory_mb": round(bf_memory_bytes / (1024 * 1024), 3),
            "build_time_sec": round(bf_build_time, 4),
            "lookup_time_sec": round(bf_lookup_time, 4),
            "avg_lookup_us": round((bf_lookup_time / lookup_trials) * 1_000_000, 3),
        },
        "python_set": {
            "memory_bytes": set_memory_bytes,
            "memory_mb": round(set_memory_bytes / (1024 * 1024), 3),
            "build_time_sec": round(set_build_time, 4),
            "lookup_time_sec": round(set_lookup_time, 4),
            "avg_lookup_us": round((set_lookup_time / lookup_trials) * 1_000_000, 3),
        },
        "memory_savings_factor": round(set_memory_bytes / bf_memory_bytes, 2) if bf_memory_bytes else None,
    }


def print_fpr_report(result):
    print("\n--- False Positive Rate Validation ---")
    print(f"Words inserted:      {result['words_inserted']:,}")
    print(f"Target FPR:          {result['target_fpr']}")
    print(f"Bits / hash funcs:   {result['num_bits']:,} / {result['num_hash_functions']}")
    print(f"Trials run:          {result['trials']:,}")
    print(f"False positives:     {result['false_positives']:,}")
    print(f"Observed FPR:        {result['observed_fpr']:.6f}")
    print(f"Theoretical FPR:     {result['theoretical_fpr']:.6f}")
    delta = abs(result['observed_fpr'] - result['theoretical_fpr'])
    print(f"Delta:               {delta:.6f}")


def print_benchmark_report(result):
    bf = result["bloom_filter"]
    s = result["python_set"]
    print("\n--- Bloom Filter vs Python set Benchmark ---")
    print(f"Word count: {result['num_words']:,}\n")
    print(f"{'Metric':<22}{'BloomFilter':<18}{'Python set':<18}")
    print(f"{'Memory (MB)':<22}{bf['memory_mb']:<18}{s['memory_mb']:<18}")
    print(f"{'Build time (s)':<22}{bf['build_time_sec']:<18}{s['build_time_sec']:<18}")
    print(f"{'Avg lookup (µs)':<22}{bf['avg_lookup_us']:<18}{s['avg_lookup_us']:<18}")
    if result["memory_savings_factor"]:
        print(f"\nBloom filter uses ~{result['memory_savings_factor']}x less memory than a Python set.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate and benchmark the Bloom filter implementation.")
    parser.add_argument('--word-file', type=str, default="words.txt", help="Source word list")
    parser.add_argument('--false-positive-rate', type=float, default=0.01)
    parser.add_argument('--limit', type=int, default=None, help="Limit number of words loaded (for faster runs)")
    parser.add_argument('--trials', type=int, default=50_000, help="Number of FPR validation trials")
    parser.add_argument('--mode', choices=["fpr", "benchmark", "both"], default="both")
    args = parser.parse_args()

    if args.mode in ("fpr", "both"):
        result = measure_false_positive_rate(
            args.word_file, args.false_positive_rate, num_trials=args.trials, limit=args.limit
        )
        print_fpr_report(result)

    if args.mode in ("benchmark", "both"):
        result = benchmark_vs_set(args.word_file, args.false_positive_rate, limit=args.limit)
        print_benchmark_report(result)
