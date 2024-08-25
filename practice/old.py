import mmh3
from bitarray import bitarray

class BloomFilter:
    def __init__(self, num_hash_functions, num_bits, filter_data=None):
        self.num_hash_functions = num_hash_functions
        self.num_bits = num_bits
        self.bit_array = bitarray(num_bits)
        self.bit_array.setall(0)
        
        if filter_data:
            if len(filter_data) * 8 < num_bits:
                raise ValueError("filter_data is too short for the number of bits.")
            self.bit_array = bitarray()
            self.bit_array.frombytes(filter_data)

    def _hash(self, item, seed):
        return mmh3.hash(key=item, seed=seed) % self.num_bits

    def add(self, item):
        for i in range(self.num_hash_functions):
            bit_index = self._hash(item, i)
            self.bit_array[bit_index] = 1

    def contains(self, item):
        for i in range(self.num_hash_functions):
            bit_index = self._hash(item, i)
            if not self.bit_array[bit_index]:
                return False
        return True
    
    def get_bytes(self):
        return self.bit_array.tobytes()

    def format_bitarray(self):
        bytes_data = self.bit_array.tobytes()
        binary_strings = [f'0b{byte:08b}' for byte in bytes_data]
        formatted_string = f'[{", ".join(binary_strings)}]'
        return formatted_string


num_hash_functions = 3
num_bits = 32

# The filter_data should be a byte-like object; use `bytes` for this purpose
# filter_data = bytes([0b00100100, 0b00110000, 0b00110000, 0b00000000])

bf = BloomFilter(num_hash_functions, num_bits, filter_data=None)

# Add some items
bf.add("example")
bf.add("test")

# Check for presence
print(bf.contains("example"))
print(bf.contains("test"))
print(bf.contains("not_in_filter"))

# Print the array
print(bf.format_bitarray())