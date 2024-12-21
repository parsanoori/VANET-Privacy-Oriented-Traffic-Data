from typing import Dict


class BlockchainNode:
    def __init__(self, blockchain: 'Blockchain'):
        self.hash_to_edge: Dict = {}
        self.edge_to_hash: Dict = {}
        self.blockchain = blockchain
        self.node_id = blockchain.get_node_id()
        blockchain.add_node(self)

    def __str__(self):
        return f"Node {self.node_id} with {len(self.blockchain)} blocks"
