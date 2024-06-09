from tqdm import tqdm
from Blockchain import Blockchain, LocalBlockchain
import networkx.readwrite.gml as gml
from typing import Dict
from typing import Optional
from utils import calc_edge_hash
import datetime
from Blockchain.BlockchainNode import BlockchainNode
from PartialHomomorphyScheme.GlobalBlockchainNode import GlobalBlockchainNode
from phe import paillier
from enum import Enum
from time import sleep
import threading
import random


class NeighborHoodState(Enum):
    FACILITATOR_REQUEST_NOT_SENT = 1
    FACILITATOR_REQUEST_SENT = 2
    FACILITATOR_REQUEST_ANSWERED = 3
    ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED = 4
    FIRST_NODE_AGGREGATED_DATA = 5
    SECOND_NODE_AGGREGATED_DATA = 6
    FIRST_NODE_PARAMETERS_SENT = 7
    SECOND_NODE_PARAMETERS_SENT = 8
    DECRYPTION_REQUEST_SENT = 9
    DECRYPTION_RESULT_RECEIVED = 10


class StreetMapAlreadyInBlockchainError(Exception):
    def __init__(self, block_index: int):
        message = "Street map is already in the blockchain at block with index " + str(block_index)
        self.message = message
        super().__init__(self.message)


class TrafficAlreadyApprovedError(Exception):
    def __init__(self):
        super().__init__("Traffic has already been approved.")


class IsNotGlobalNodeError(Exception):
    def __init__(self, node):
        self.node = node
        self.message = f"Node {node} is not a global node"
        super().__init__(self.message)


class IncorrectStateForAction(Exception):
    def __init__(self, state: NeighborHoodState, action: str):
        self.state = state
        self.action = action
        self.message = f"State {state} is incorrect for action {action}"
        super().__init__(self.message)


class LocalBlockchainNode(BlockchainNode):
    def __init__(self, local_blockchain: LocalBlockchain, global_blockchain: Optional[Blockchain] = None,
                 sleep_time: float = 0.2, traffic_update_interval_in_seconds: int = 10, quiet=False):
        # local blockchain node is primarily a local blockchain node, but it can also be a global blockchain node too
        neighborhood = local_blockchain.neighborhood
        BlockchainNode.__init__(self, local_blockchain)
        self.global_blockchain = global_blockchain
        self.global_node = GlobalBlockchainNode(global_blockchain) if global_blockchain is not None else None
        self.neighborhood = neighborhood
        self.street_graph = gml.read_gml("./graphs/" + neighborhood + ".gml")
        self.street_graph_edges_forward: Dict = {}
        self.street_graph_edges_backward: Dict = {}
        self.add_street_data_to_node()
        self.state: NeighborHoodState = NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT
        self.state_lock = threading.Lock()
        self.last_state_update: datetime.datetime = datetime.datetime.now()
        self.facilitator_pubkey = None
        self.facilitator_response_time = None
        self.neighborhood_encrypted_traffic = None
        self.state_thread = threading.Thread(target=self.update_state_periodically)
        self.forward_related_blocks_thread = threading.Thread(target=self.forward_related_blocks_periodically)
        self.system_running = True
        self.debug = False
        self.a: int = 0
        self.b: int = 0
        self.c: int = 0
        self.d: int = 0
        self.first_node: bool = False
        self.slope: int = 0
        self.bias: int = 0
        self.f_ab_average_traffic: Dict[str, int] = {}
        self.f_cd_average_traffic: Dict[str, int] = {}
        self.raw_decrypted_traffic: Dict[str, int] = {}
        self.quiet = quiet
        self.encrypted_traffic_block_size: int = 0
        self.traffic_log_size: int = 0
        self.calculating_traffic_log_encryption_time = None
        self.calculating_encrypted_average_time = None
        self.sleep_time = sleep_time
        self.traffic_update_interval_in_seconds = traffic_update_interval_in_seconds

    def run_threaded(self):
        if self.global_node is not None:
            self.forward_related_blocks_thread.start()
            self.state_thread.start()
            return [self.state_thread, self.forward_related_blocks_thread]
        else:
            self.state_thread.start()
            return self.state_thread

    def update_state_periodically(self):
        while self.system_running:
            self.update_state()
            sleep(self.sleep_time)

    def forward_related_blocks_periodically(self):
        while self.system_running:
            self.forward_global_related_blocks()
            sleep(self.sleep_time)

    def update_state(self):
        self.state_lock.acquire()
        block = self.blockchain.tail
        if block is None:
            self.state = NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT
        block_type = block.data["type"]
        if block_type == "request_facilitator":
            if self.state == NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Facilitator request received. Now facilitator should respond")
            self.state = NeighborHoodState.FACILITATOR_REQUEST_SENT
        elif block_type == "facilitator_accepted_request":
            if self.state == NeighborHoodState.FACILITATOR_REQUEST_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: "
                          f"Facilitator accepted request.")
            self.state = NeighborHoodState.FACILITATOR_REQUEST_ANSWERED
            self.update_facilitator_data(block)
        elif self.state == NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            if self.facilitator_response_time + datetime.timedelta(
                    seconds=self.traffic_update_interval_in_seconds) < datetime.datetime.now():
                if self.state == NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
                    if not self.quiet:
                        print(
                            f"Local node {self.node_id}: Traffic update interval reached. Now first node should send encrypted average traffic.")
                self.state = NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED
        elif block_type == "f_ab_encrypted_average_traffic":
            if self.state == NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
                if not self.quiet:
                    print(
                        f"Local node {self.node_id}: First Node Aggregated Data Received. Now second node Parameters should be sent.")
            self.state = NeighborHoodState.FIRST_NODE_AGGREGATED_DATA
        elif block_type == "f_cd_encrypted_average_traffic":
            if self.state == NeighborHoodState.FIRST_NODE_AGGREGATED_DATA:
                if not self.quiet:
                    print(
                        f"Local node {self.node_id}: Second Node Aggregated Data Received. Now first node Parameters should be sent.")
            self.state = NeighborHoodState.SECOND_NODE_AGGREGATED_DATA
        elif block_type == "first_node_parameters":
            self.a = int(block.data["a"])
            self.b = int(block.data["b"])
            if self.a == 0:
                raise ValueError("a is 0")
            if self.b == 0:
                raise ValueError("b is 0")
            if self.state == NeighborHoodState.SECOND_NODE_AGGREGATED_DATA:
                if not self.quiet:
                    print(
                        f'Local node {self.node_id}: First Node Parameters Received. a: {self.a}, b: {self.b}. Now the second parameters shoudl be sent')
                self.state = NeighborHoodState.FIRST_NODE_PARAMETERS_SENT
        elif block_type == "second_node_parameters":
            self.c = int(block.data["c"])
            self.d = int(block.data["d"])
            if self.c == 0:
                raise ValueError("c is 0")
            if self.d == 0:
                raise ValueError("d is 0")
            if self.state == NeighborHoodState.FIRST_NODE_PARAMETERS_SENT:
                if not self.quiet:
                    print(
                        f'Local node {self.node_id}: Second Node Parameters Received. c: {self.c}, d: {self.d}. Now the decryption request should be sent.')
                self.state = NeighborHoodState.SECOND_NODE_PARAMETERS_SENT
        elif block_type == "send_decryption":
            if self.state == NeighborHoodState.SECOND_NODE_PARAMETERS_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Decryption request received. Now the decryption should be sent.")
            self.state = NeighborHoodState.DECRYPTION_REQUEST_SENT
        elif block_type == "decrypted_average_traffic":
            if self.state == NeighborHoodState.DECRYPTION_REQUEST_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Decrypted average traffic received.")
            self.state = NeighborHoodState.DECRYPTION_RESULT_RECEIVED
            self.save_average_traffic(block)
        elif block_type == "approved" or block_type == "disapproved":
            if self.state == NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Results {block_type}.")
            self.state = NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT
        self.state_lock.release()

    def forward_global_block(self, block):
        if self.global_node is None:
            raise IsNotGlobalNodeError
        self.blockchain.add_block(block)

    def forward_global_related_blocks(self):
        if self.global_node is None:
            raise IsNotGlobalNodeError
        block = self.global_node.blockchain.tail
        global_block_type = block["type"]
        if "neighborhood" not in block.data or block.data["neighborhood"] != self.neighborhood:
            return
        self.update_state()
        state = self.state
        if state == NeighborHoodState.FACILITATOR_REQUEST_SENT and global_block_type == "facilitator_accepted_request":
            self.forward_global_block(block.data)
        elif state == NeighborHoodState.DECRYPTION_REQUEST_SENT and global_block_type == "decrypted_average_traffic":
            self.forward_global_block(block.data)
        else:
            return
        self.update_state()

    def __str__(self):
        if self.global_node is None:
            return f"Local Node {self.node_id}"
        else:
            return f"Local Node {self.node_id} and Global Node {self.global_node.node_id}"

    def get_node_state(self):
        return self.state

    def add_street_graph_edges_to_blockchain(self):
        index = 0
        for block in self.blockchain:
            if block.data["type"] == "street_graph":
                raise StreetMapAlreadyInBlockchainError(index)
            index += 1
        if not self.street_graph_edges_forward:
            self.add_street_data_to_node()
        street_graph_edges_block = {
            "type": "street_graph",
            "edges": list(self.street_graph_edges_forward.keys())
        }
        self.blockchain.add_block(street_graph_edges_block)
        return street_graph_edges_block

    def add_street_data_to_node(self):
        street_graph_edges = list(self.street_graph.edges)
        for edge in street_graph_edges:
            edge_hash = calc_edge_hash(edge)
            self.street_graph_edges_forward[edge_hash] = edge
            self.street_graph_edges_backward[edge] = edge_hash

    # step 1
    def request_facilitating(self):
        self.update_state()
        if self.state != NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT:
            raise IncorrectStateForAction(self.state, "request_facilitating")
        if self.global_node is None:
            raise
        request_facilitator_block = {
            "type": "request_facilitator",
            "neighborhood": self.neighborhood
        }
        self.global_node.blockchain.add_block(request_facilitator_block)
        self.blockchain.add_block(request_facilitator_block)
        return request_facilitator_block

    # step 2 is handled by the facilitator

    # step 3
    def send_encrypted_traffic_log(self, edge, speed):
        self.update_state()
        if self.state != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            raise IncorrectStateForAction(self.state, "send_encrypted_traffic_log")
        edge_hash = self.street_graph_edges_backward[edge]
        start = datetime.datetime.now()
        encrypted_speed = self.facilitator_pubkey.encrypt(speed)
        ciphertext = encrypted_speed.ciphertext()
        exponent = encrypted_speed.exponent
        traffic_speed_block = {
            "type": "encrypted_traffic_log",
            "edge_hash": edge_hash,
            "speed": (ciphertext, exponent)
        }
        end = datetime.datetime.now()
        self.calculating_traffic_log_encryption_time = end - start
        self.blockchain.add_block(traffic_speed_block)
        self.traffic_log_size = len(str(traffic_speed_block))
        return traffic_speed_block

    # ================== step 4&5 ==================
    def generate_parameters(self):
        self.slope = random.randint(1, 100)
        self.bias = random.randint(1, 100)

    def _get_edge_average_speed(self, edge) -> paillier.EncryptedNumber:
        edge_hash = self.street_graph_edges_backward[edge]
        block = self.blockchain.tail
        speeds = self.facilitator_pubkey.encrypt(0)
        count = 0
        while block is not None and block.timestamp > self.facilitator_response_time:
            if block.data["type"] == "traffic_speed" and block.data["edge_hash"] == edge_hash:
                ciphertext, exponent = block.data["speed"]
                speed = paillier.EncryptedNumber(self.facilitator_pubkey, ciphertext, exponent)
                speeds += speed
                count += 1
            block = block.previous_block
        if count == 0:
            raw_average = self.facilitator_pubkey.encrypt(100)
        else:
            raw_average = speeds / count
        f_average_edge_speed = raw_average * self.slope + self.bias
        return f_average_edge_speed

    def _calculate_neighborhood_encrypted_average_traffic(self):
        traffic = {}
        for edge in tqdm(self.street_graph.edges):
            edge_average_speed = self._get_edge_average_speed(edge)
            ciphertext = edge_average_speed.ciphertext()
            exponent = edge_average_speed.exponent
            traffic[calc_edge_hash(edge)] = (ciphertext, exponent)
        return traffic

    def add_traffic_to_chains(self):
        self.update_state()
        if self.state == NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
            self.first_node = True
        elif self.state == NeighborHoodState.FIRST_NODE_AGGREGATED_DATA:
            self.first_node = False
        else:
            raise IncorrectStateForAction(self.state, "add_traffic_to_localchain")

        self.generate_parameters()

        start = datetime.datetime.now()
        traffic = self._calculate_neighborhood_encrypted_average_traffic()
        end = datetime.datetime.now()
        self.calculating_encrypted_average_time = end - start
        if not self.quiet:
            print(f"Local node {self.node_id}: Calculated encrypted average traffic in {end - start} seconds")
        traffic_block = {
            "type": "f_ab_encrypted_average_traffic" if self.first_node else "f_cd_encrypted_average_traffic",
            "average_traffic": traffic
        }
        self.blockchain.add_block(traffic_block)
        traffic_block["neighborhood"] = self.neighborhood
        length = len(str(traffic_block))
        self.encrypted_traffic_block_size = length
        self.global_node.blockchain.add_block(traffic_block)

    # ================ end of step 4&5 ================

    # ================ step 6&7 ================
    def send_parameters(self):
        self.update_state()
        if self.state != NeighborHoodState.SECOND_NODE_AGGREGATED_DATA and self.state != NeighborHoodState.FIRST_NODE_PARAMETERS_SENT:
            raise IncorrectStateForAction(self.state, "approve_traffic_encrypted")
        if self.first_node:
            self.blockchain.add_block({
                "type": "first_node_parameters",
                "a": self.slope,
                "b": self.bias
            })
        else:
            self.blockchain.add_block({
                "type": "second_node_parameters",
                "c": self.slope,
                "d": self.bias
            })

    # ============== end of step 6&7 ==============

    # ============== step 8 ==============
    def send_decryption_request(self):
        if self.global_node is None:
            raise IsNotGlobalNodeError
        self.update_state()
        if self.state != NeighborHoodState.SECOND_NODE_PARAMETERS_SENT:
            raise IncorrectStateForAction(self.state, "send_decryption_request")
        data = {
            "type": "send_decryption",
        }
        self.blockchain.add_block(data)
        data["neighborhood"] = self.neighborhood
        self.global_node.blockchain.add_block(data)

    # ============== end of step 8 ==============

    # ============== step 9 ==============
    # step 9 is handled by the facilitator
    # ============== end of step 9 ==============

    # ============== step 10 ==============
    def approve_results(self):
        self.update_state()
        if self.state != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
            raise IncorrectStateForAction(self.state, "approve_results")

        raw_decrypted_traffic = {}
        for key, value in tqdm(self.f_ab_average_traffic.items()):
            if key not in self.f_cd_average_traffic:
                if not self.quiet:
                    print(f'key {key} not in f_cd_average_traffic')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False
            raw_node_one = (value - self.b) / self.a
            node_two_value = self.f_cd_average_traffic[key]
            raw_node_two = (node_two_value - self.d) / self.c
            if raw_node_one != raw_node_two:
                if not self.quiet:
                    print(f'raw_node_one {raw_node_one} != raw_node_two {raw_node_two}')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False
            raw_decrypted_traffic[key] = raw_node_one

        for key, value in tqdm(self.f_cd_average_traffic.items()):
            if key not in self.f_ab_average_traffic:
                print(f'key {key} not in f_ab_average_traffic')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False

        self.blockchain.add_block({
            "type": "approved"
        })
        self.raw_decrypted_traffic = raw_decrypted_traffic
        return raw_decrypted_traffic

    # ============== end of step 10 ==============

    def update_facilitator_data(self, block):
        self.facilitator_pubkey = paillier.PaillierPublicKey(int(block.data["public_key"]))
        self.facilitator_response_time = block.timestamp

    def save_average_traffic(self, block):
        for key, value in block.data["f_ab_decrypted_average_traffic"].items():
            self.f_ab_average_traffic[key] = int(value)
        for key, value in block.data["f_cd_decrypted_average_traffic"].items():
            self.f_cd_average_traffic[key] = int(value)
