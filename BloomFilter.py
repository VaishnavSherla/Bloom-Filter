import mmh3
from bitarray import bitarray
import math
import pickle

class BloomFilter:
    def __init__(self, num_hash_functions=None, num_bits=None, filter_data=None):
        if num_hash_functions is None or num_bits is None:
            raise ValueError("num_hash_functions and num_bits must be provided during initialization.")
        
        self.num_hash_functions = num_hash_functions
        self.num_bits = num_bits
        self.bit_array = bitarray(num_bits)
        self.bit_array.setall(0)
        
        if filter_data:
            if len(filter_data) * 8 < num_bits:
                raise ValueError("filter_data is too short for the number of bits.")
            self.bit_array = bitarray()
            self.bit_array.frombytes(filter_data)
    
    @staticmethod
    def optimal_parameters(num_elements, false_positive_rate):
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
    
    def save(self, filename):
        try:
            with open(filename, 'wb') as f:
                # Save parameters and filter data
                pickle.dump((self.num_hash_functions, self.num_bits, self.get_bytes()), f)
        except Exception as e:
            print(f"An error occurred while saving the file: {e}")
    
    def load_from_file(self, filename):
        try:
            with open(filename, 'rb') as f:
                num_hash_functions, num_bits, filter_data = pickle.load(f)
                self.__init__(num_hash_functions, num_bits, filter_data)
        except FileNotFoundError:
            print(f"File {filename} not found.")
        except Exception as e:
            print(f"An error occurred while loading the file: {e}")
