import argparse
import json

from BloomFilter import BloomFilter
from ScalableBloomFilter import ScalableBloomFilter

FILTER_FILE = "words.dat"
SCALABLE_FILTER_FILE = "words_scalable.dat"
CONFIG_FILE = "config.json"


def count_words(file):
    try:
        with open(file, 'r') as f:
            word_count = sum(len(line.split()) for line in f)
        return word_count
    except FileNotFoundError:
        print(f"File {file} not found.")
        return 0
    except Exception as e:
        print(f"An error occurred: {e}")
        return 0


def save_config(num_hash_functions, num_bits):
    config = {
        "num_hash_functions": num_hash_functions,
        "num_bits": num_bits
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    print(f"Configuration saved to {CONFIG_FILE}")


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config["num_hash_functions"], config["num_bits"]
    except FileNotFoundError:
        print(f"Configuration file {CONFIG_FILE} not found.")
        return None, None
    except json.JSONDecodeError:
        print(f"Error decoding configuration file {CONFIG_FILE}.")
        return None, None
    except KeyError as e:
        print(f"Missing key in configuration file: {e}")
        return None, None


def build_command(word_file, false_positive_rate, num_elements=None, scalable=False, growth_threshold=0.5):
    num_elements = num_elements if num_elements else count_words(word_file)

    if num_elements <= 0:
        print("Error: Number of elements must be greater than zero.")
        return

    if scalable:
        sbf = ScalableBloomFilter(
            initial_capacity=num_elements,
            false_positive_rate=false_positive_rate,
            growth_threshold=growth_threshold,
        )
        sbf.build(word_file)
        sbf.save(SCALABLE_FILTER_FILE)
        stats = sbf.stats()
        print(f"Scalable Bloom filter built with {stats['num_filters']} filter(s), "
              f"{stats['total_bits']:,} total bits, {stats['total_inserted']:,} elements inserted.")
        print(f"Saved to {SCALABLE_FILTER_FILE}")
        return

    num_bits, num_hash_functions = BloomFilter.optimal_parameters(num_elements, false_positive_rate)
    bloom_filter = BloomFilter(num_hash_functions, num_bits)
    bloom_filter.build(word_file)
    bloom_filter.save(FILTER_FILE)
    save_config(num_hash_functions, num_bits)
    print(f"Bloom filter built with {num_bits} bits and {num_hash_functions} hash functions.")
    print(f"Bloom filter saved to {FILTER_FILE}")


def check_command(words, scalable=False):
    if scalable:
        try:
            sbf = ScalableBloomFilter.load_from_file(SCALABLE_FILTER_FILE)
        except FileNotFoundError:
            print(f"Scalable filter file {SCALABLE_FILTER_FILE} not found. Run -build --scalable first.")
            return
        incorrect_words = [word for word in words if not sbf.contains(word)]
    else:
        num_hash_functions, num_bits = load_config()
        if num_hash_functions is None or num_bits is None:
            print("Error loading Bloom filter configuration.")
            return

        bloom_filter = BloomFilter(num_hash_functions, num_bits)
        bloom_filter.load_from_file(FILTER_FILE)
        incorrect_words = [word for word in words if not bloom_filter.contains(word)]

    if incorrect_words:
        print("These words are spelt wrong:")
        for word in incorrect_words:
            print(f"{word}")
    else:
        print("All words are correctly identified.")


def stats_command(scalable=False):
    """
    Prints fill ratio and live estimated false-positive rate.
    This is the early-warning signal for filter saturation in production:
    once fill_ratio crosses ~0.5 the estimated FPR starts climbing sharply,
    which is exactly the point a real system would either rotate to a new
    filter (see --scalable) or trigger a full rebuild.
    """
    if scalable:
        try:
            sbf = ScalableBloomFilter.load_from_file(SCALABLE_FILTER_FILE)
        except FileNotFoundError:
            print(f"Scalable filter file {SCALABLE_FILTER_FILE} not found. Run -build --scalable first.")
            return
        stats = sbf.stats()
        print("\n--- Scalable Bloom Filter Stats ---")
        print(f"Number of filters in chain: {stats['num_filters']}")
        print(f"Growth threshold:            {stats['growth_threshold']}")
        print(f"Total bits across chain:     {stats['total_bits']:,}")
        print(f"Total elements inserted:     {stats['total_inserted']:,}\n")
        for i, f in enumerate(stats["filters"]):
            marker = " (active)" if i == len(stats["filters"]) - 1 else ""
            print(f"Filter {i}{marker}:")
            print(f"  bits={f['num_bits']:,}  hashes={f['num_hash_functions']}  "
                  f"inserted={f['num_inserted']:,}  fill_ratio={f['fill_ratio']}  "
                  f"est_fpr={f['estimated_fpr']}")
        return

    num_hash_functions, num_bits = load_config()
    if num_hash_functions is None or num_bits is None:
        print("Error loading Bloom filter configuration.")
        return

    bloom_filter = BloomFilter(num_hash_functions, num_bits)
    try:
        bloom_filter.load_from_file(FILTER_FILE)
    except FileNotFoundError:
        print(f"Filter file {FILTER_FILE} not found. Run -build first.")
        return

    s = bloom_filter.stats()
    print("\n--- Bloom Filter Stats ---")
    print(f"Bits:                  {s['num_bits']:,}")
    print(f"Hash functions:        {s['num_hash_functions']}")
    print(f"Elements inserted:     {s['num_inserted']:,}")
    print(f"Fill ratio:            {s['fill_ratio']}")
    print(f"Estimated live FPR:    {s['estimated_fpr']}")

    if s["fill_ratio"] >= 0.5:
        print("\n⚠  Fill ratio has crossed 50% — false-positive rate is rising sharply.")
        print("   Consider rebuilding, or switch to --scalable to chain a fresh filter automatically.")


def main():
    parser = argparse.ArgumentParser(description="Spellcheck with Bloom filter.")
    parser.add_argument('-build', type=str, help='File containing words to add to the Bloom filter')
    parser.add_argument('-check', nargs='+', help='Words to check against the Bloom filter')
    parser.add_argument('--false-positive-rate', type=float, default=0.01, help='Desired false positive rate (default: 0.01)')
    parser.add_argument('--num-elements', type=int, help='Number of elements expected in the Bloom filter')
    parser.add_argument('--scalable', action='store_true',
                         help='Use the scalable (chained) Bloom filter instead of a single fixed-size filter')
    parser.add_argument('--growth-threshold', type=float, default=0.5,
                         help='Fill ratio at which the scalable filter grows a new chain link (default: 0.5)')
    parser.add_argument('-stats', action='store_true', help='Show fill ratio and live estimated false-positive rate')

    args = parser.parse_args()

    if args.build:
        build_command(args.build, args.false_positive_rate, args.num_elements, args.scalable, args.growth_threshold)
    elif args.check:
        check_command(args.check, args.scalable)
    elif args.stats:
        stats_command(args.scalable)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
