import mmh3
from bitarray import bitarray
import math
import pickle


class BloomFilter:
    """
    Standard Bloom filter backed by a bitarray and k seeded MurmurHash3 calls.

    Tracks its own insertion count so callers (e.g. ScalableBloomFilter) can
    query fill ratio and live false-positive estimates without re-deriving
    them externally.
    """

    def __init__(self, num_hash_functions=None, num_bits=None, filter_data=None, num_inserted=0):
        if num_hash_functions is None or num_bits is None:
            raise ValueError("num_hash_functions and num_bits must be provided during initialization.")

        self.num_hash_functions = num_hash_functions
        self.num_bits = num_bits
        self.num_inserted = num_inserted
        self.bit_array = bitarray(num_bits)
        self.bit_array.setall(0)

        if filter_data:
            if len(filter_data) * 8 < num_bits:
                raise ValueError("filter_data is too short for the number of bits.")
            self.bit_array = bitarray()
            self.bit_array.frombytes(filter_data)

    @staticmethod
    def optimal_parameters(num_elements, false_positive_rate):
        """
        m = -(n * ln(p)) / (ln(2))^2
        k = (m / n) * ln(2)
        """
        num_bits = math.ceil(-num_elements * math.log(false_positive_rate) / (math.log(2) ** 2))
        num_hash_functions = max(1, round(math.log(2) * num_bits / num_elements))
        return num_bits, num_hash_functions

    def _hash(self, item, seed):
        item_bytes = item.encode('utf-8')
        return mmh3.hash(key=item_bytes, seed=seed) % self.num_bits

    def add(self, item):
        item = item.lower()
        for i in range(self.num_hash_functions):
            bit_index = self._hash(item, i)
            self.bit_array[bit_index] = 1
        self.num_inserted += 1

    def contains(self, item):
        item = item.lower()
        for i in range(self.num_hash_functions):
            bit_index = self._hash(item, i)
            if not self.bit_array[bit_index]:
                return False
        return True

    def get_bytes(self):
        return self.bit_array.tobytes()

    def build(self, file):
        try:
            with open(file, 'r') as f:
                for line in f:
                    self.add(line.strip().lower())
        except FileNotFoundError:
            print(f"File {file} not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    # ---- Production-awareness: fill ratio + live FPR estimate -------------

    def fill_ratio(self):
        """Fraction of bits currently set to 1. The key early-warning signal
        for filter saturation — independent of how many elements you *think*
        you've inserted, this tells you the actual state of the array."""
        return self.bit_array.count(1) / self.num_bits

    def estimated_false_positive_rate(self):
        """
        Theoretical FPR given current fill ratio:
            p = (fill_ratio) ^ k
        This is the textbook formula evaluated against the *actual* current
        state of the bit array, not the target FPR it was built for — so it
        reflects drift as more elements get inserted than originally planned.
        """
        return self.fill_ratio() ** self.num_hash_functions

    def stats(self):
        return {
            "num_bits": self.num_bits,
            "num_hash_functions": self.num_hash_functions,
            "num_inserted": self.num_inserted,
            "fill_ratio": round(self.fill_ratio(), 6),
            "estimated_fpr": round(self.estimated_false_positive_rate(), 8),
        }

    def save(self, filename):
        try:
            with open(filename, 'wb') as f:
                pickle.dump(
                    (self.num_hash_functions, self.num_bits, self.get_bytes(), self.num_inserted),
                    f,
                )
        except Exception as e:
            print(f"An error occurred while saving the file: {e}")

    def load_from_file(self, filename):
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                # Backward-compatible with old 3-tuple files (no num_inserted)
                if len(data) == 4:
                    num_hash_functions, num_bits, filter_data, num_inserted = data
                else:
                    num_hash_functions, num_bits, filter_data = data
                    num_inserted = 0
                self.__init__(num_hash_functions, num_bits, filter_data, num_inserted)
        except FileNotFoundError:
            print(f"File {filename} not found.")
        except Exception as e:
            print(f"An error occurred while loading the file: {e}")
