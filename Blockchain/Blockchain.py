from .Block import Block
from .BlockchainNode import BlockchainNode
from typing import List


class Blockchain:
    def __init__(self):
        # create the first block
        self.head: Block = Block(0, '0', {"type": "genesis"}, None, None)
        self.tail: Block = self.head
        self.length = 1
        self.nodes: List['BlockchainNode'] = []
        self.nodesCount = 0

    def add_block(self, data: dict):
        new_block = Block(self.length, self.tail.hash, data, None, self.tail)
        self.tail.next_block = new_block
        self.tail = new_block
        self.length += 1

    def validate_chain(self):
        current = self.head
        while current.next_block is not None:
            if current.next_block.previous_hash != current.hash:
                return False
            if current.calc_hash() != current.hash:
                return False
            current = current.next_block
        return True

    def __str__(self):
        return f"Blockchain with {self.length} blocks"

    def __repr__(self):
        return f"Blockchain with {self.length} blocks"

    def __iter__(self):
        self.current = self.head
        return self

    def __next__(self):
        if self.current is None:
            raise StopIteration
        else:
            result = self.current
            self.current = self.current.next_block
            return result

    def __getitem__(self, index):
        current = self.head
        for i in range(index):
            current = current.next_block
        return current

    def __len__(self):
        return self.length

    def __eq__(self, other):
        return self.head == other.head and self.tail == other.tail

    def __ne__(self, other):
        return self.head != other.head or self.tail != other.tail

    def __add__(self, other):
        new_blockchain = Blockchain()
        for block in self:
            new_blockchain.add_block(block.data)
        for block in other:
            new_blockchain.add_block(block.data)
        return new_blockchain

    def __iadd__(self, other):
        for block in other:
            self.add_block(block.data)
        return self

    def __contains__(self, item):
        for block in self:
            if block == item:
                return True
        return False

    def get_node_id(self):
        old_count = self.nodesCount
        self.nodesCount += 1
        return old_count

    def add_node(self, node: 'BlockchainNode'):
        self.nodes.append(node)

    def get_data_size(self):
        size = 0
        block = self.head.next_block
        while block is not None:
            size += len(str(block.data))
            block = block.next_block
        return size
