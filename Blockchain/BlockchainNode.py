from typing import Dict


class BlockchainNode:
    def __init__(self, blockchain: 'Blockchain'):
        self.street_graph_edges_forward: Dict = {}
        self.street_graph_edges_backward: Dict = {}
        self.blockchain = blockchain
        self.node_id = blockchain.get_node_id()
        blockchain.add_node(self)

    def __str__(self):
        return f"Node {self.node_id} with {len(self.blockchain)} blocks"
