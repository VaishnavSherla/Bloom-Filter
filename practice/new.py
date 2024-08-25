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

    def format_bitarray(self):
        bytes_data = self.bit_array.tobytes()
        binary_strings = [f'0b{byte:08b}' for byte in bytes_data]
        return f'[{", ".join(binary_strings)}]'

    def build(self, file):
        with open(file, 'r') as f:
            for line in f:
                self.add(line.strip().lower())
    
    def save(self, filename):
        with open(filename, 'wb') as f:
            f.write(self.get_bytes())
    
    def load_from_file(self, filename):
        with open(filename, 'rb') as f:
            filter_data = f.read()
        self.__init__(self.num_hash_functions, self.num_bits, filter_data)

num_hash_functions = 13
num_bits = 8943818

bf = BloomFilter(num_hash_functions, num_bits)

bf.build('words.txt')

bf.save('bloom.dat')

loaded_bf = BloomFilter(num_hash_functions, num_bits)

loaded_bf.load_from_file('bloom.dat')

print(loaded_bf.contains("example"))
print(loaded_bf.contains("test"))
print(loaded_bf.contains("coding"))
print(loaded_bf.contains("cosding"))
