import argparse
import json
from BloomFilter import BloomFilter

FILTER_FILE = "words.dat"
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

def build_command(word_file, false_positive_rate, num_elements=None):
    num_elements = num_elements if num_elements else count_words(word_file)
    
    if num_elements <= 0:
        print("Error: Number of elements must be greater than zero.")
        return
    
    num_bits, num_hash_functions = BloomFilter.optimal_parameters(num_elements, false_positive_rate)
    bloom_filter = BloomFilter(num_hash_functions, num_bits)
    bloom_filter.build(word_file)
    bloom_filter.save(FILTER_FILE)
    save_config(num_hash_functions, num_bits)  # Save parameters to config
    print(f"Bloom filter built with {num_bits} bits and {num_hash_functions} hash functions.")
    print(f"Bloom filter saved to {FILTER_FILE}")

def check_command(words):
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

def main():
    parser = argparse.ArgumentParser(description="Spellcheck with Bloom filter.")
    parser.add_argument('-build', type=str, help='File containing words to add to the Bloom filter')
    parser.add_argument('-check', nargs='+', help='Words to check against the Bloom filter')
    parser.add_argument('--false-positive-rate', type=float, default=0.01, help='Desired false positive rate (default: 0.01)')
    parser.add_argument('--num-elements', type=int, help='Number of elements expected in the Bloom filter')

    args = parser.parse_args()
    
    if args.build:
        build_command(args.build, args.false_positive_rate, args.num_elements)
    elif args.check:
        check_command(args.check)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
