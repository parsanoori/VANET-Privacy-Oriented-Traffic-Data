import hashlib
from typing import Union, List, Dict, Any, Optional
import datetime


class Block:
    def __init__(self, index: int, previous_hash: str, data: Dict, next_block: Optional['Block'],
                 previous_block: Optional['Block']):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = datetime.datetime.now()
        self.data = data
        self.next_block = next_block
        self.previous_block = previous_block
        self.hash = self.calc_hash()

    def calc_hash(self):
        sha = hashlib.sha256()
        sha.update(str(self.index).encode('utf-8') +
                   str(self.previous_hash).encode('utf-8') +
                   str(self.timestamp).encode('utf-8') +
                   str(self.data).encode('utf-8'))
        return sha.hexdigest()

    def __str__(self):
        return f"Block {self.index} with hash {self.hash} and previous hash {self.previous_hash}"

    def __repr__(self):
        return f"Block {self.index} with hash {self.hash} and previous hash {self.previous_hash}"

    def __eq__(self, other):
        return self.hash == other.hash

    def __ne__(self, other):
        return self.hash != other.hash

    def __getitem__(self, item):
        return self.data[item]
