from tqdm import tqdm
from Blockchain import Blockchain, LocalBlockchain
import networkx.readwrite.gml as gml
from typing import Dict, Tuple, Optional
from utils import calc_edge_hash, b64_enc, b64_dec
import datetime
from Blockchain.BlockchainNode import BlockchainNode
from PartialHomomorphyScheme.GlobalBlockchainNode import GlobalBlockchainNode
from enum import Enum
from time import sleep
import threading
import random
import tenseal as ts


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
                 sleep_time: float = 0.2, update_interval: int = 10, quiet=False):
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
        self.facilitator_ctx: ts.Context = None
        self.facilitator_response_time = None
        self.encrypted_data = None
        self.state_thread = threading.Thread(target=self.update_state_periodically)
        self.forwarding_thread = threading.Thread(target=self.forward_related_blocks_periodically)
        self.system_running = True
        self.debug = False
        self.a: int = 0
        self.b: int = 0
        self.first_node: bool = False
        self.max_speed: int = 100
        self.max_cars: int = 100
        self.error: int = 0
        self.f_a: Dict[str, Tuple[int, int]] = {}
        self.f_b: Dict[str, Tuple[int, int]] = {}
        self.speeds_count_per_street: Dict = {}
        self.decrypted_traffic: Dict[str, Tuple[int, int]] = {}
        self.quiet = quiet
        self.encrypted_traffic_block_size: int = 0
        self.log_size: int = 0
        self.log_encryption_time = None
        self.aggregation_time = None
        self.sleep_time = sleep_time
        self.update_interval = update_interval  # in seconds

    def run_threaded(self):
        if self.global_node is not None:
            self.forwarding_thread.start()
            self.state_thread.start()
            return [self.state_thread, self.forwarding_thread]
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
                    seconds=self.update_interval) < datetime.datetime.now():
                if self.state == NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
                    if not self.quiet:
                        print(
                            f"Local node {self.node_id}: Traffic update interval reached. Now first node should send encrypted traffic data.")
                self.state = NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED
        elif block_type == "f_a_encrypted":
            if self.state == NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
                if not self.quiet:
                    print(
                        f"Local node {self.node_id}: First Node Aggregated Data Received. Now first node shoud send encrypted traffic data.")
            self.state = NeighborHoodState.FIRST_NODE_AGGREGATED_DATA
        elif block_type == "f_b_encrypted":
            if self.state == NeighborHoodState.FIRST_NODE_AGGREGATED_DATA:
                if not self.quiet:
                    print(
                        f"Local node {self.node_id}: Second Node Aggregated Data Received. Now first node Parameters should be sent.")
            self.state = NeighborHoodState.SECOND_NODE_AGGREGATED_DATA
        elif block_type == "first_node_parameters":
            self.a = int(block.data["a"])
            if self.a == 0:
                raise ValueError("a is 0")
            if self.state == NeighborHoodState.SECOND_NODE_AGGREGATED_DATA:
                if not self.quiet:
                    print(
                        f'Local node {self.node_id}: First Node Parameters Received. a: {self.a}. Now the second parameters should be sent')
                self.state = NeighborHoodState.FIRST_NODE_PARAMETERS_SENT
        elif block_type == "second_node_parameters":
            self.b = int(block.data["b"])
            if self.b == 0:
                raise ValueError("b is 0")
            if self.state == NeighborHoodState.FIRST_NODE_PARAMETERS_SENT:
                if not self.quiet:
                    print(
                        f'Local node {self.node_id}: Second Node Parameters Received. b: {self.b}.')
                self.state = NeighborHoodState.SECOND_NODE_PARAMETERS_SENT
        elif block_type == "send_decryption":
            if self.state == NeighborHoodState.SECOND_NODE_PARAMETERS_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Decryption request received. Now the decryption should be sent.")
            self.state = NeighborHoodState.DECRYPTION_REQUEST_SENT
        elif block_type == "decrypted_data":
            if self.state == NeighborHoodState.DECRYPTION_REQUEST_SENT:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Decrypted traffic data received.")
            self.state = NeighborHoodState.DECRYPTION_RESULT_RECEIVED
            self.save_traffic(block)
        elif block_type == "approved" or block_type == "disapproved":
            if self.state == NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
                if not self.quiet:
                    print(f"Local node {self.node_id}: Results {block_type}.")
            self.state = NeighborHoodState.FACILITATOR_REQUEST_NOT_SENT
        self.state_lock.release()

    def forward_raw_traffic(self, data):
        if self.global_node is None:
            raise IsNotGlobalNodeError
        data["neighborhood"] = self.neighborhood
        self.global_blockchain.add_block(data)

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
        elif state == NeighborHoodState.DECRYPTION_REQUEST_SENT and global_block_type == "decrypted_data":
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
    def send_encrypted_log(self, edge, speed):
        self.update_state()
        if self.state != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            raise IncorrectStateForAction(self.state, "send_encrypted_traffic_log")
        edge_hash = self.street_graph_edges_backward[edge]
        start = datetime.datetime.now()
        ciphertext = b64_enc(ts.bfv_vector(self.facilitator_ctx, [speed]).serialize())
        traffic_speed_block = {
            "type": "encrypted_log",
            "edge_hash": edge_hash,
            "speed": ciphertext
        }
        end = datetime.datetime.now()
        self.log_encryption_time = end - start
        self.blockchain.add_block(traffic_speed_block)
        self.log_size = len(str(traffic_speed_block))
        return traffic_speed_block

    # ================== step 4&5 ==================
    def generate_parameters(self):
        self.error = random.randint(-10_000, 10_000)

    def _get_edge_data(self, edge):
        edge_hash = self.street_graph_edges_backward[edge]
        block = self.blockchain.tail
        speeds = ts.bfv_vector(self.facilitator_ctx, [self.error])
        sqspeeds = ts.bfv_vector(self.facilitator_ctx, [self.error])
        count = 0
        while block is not None and block.timestamp > self.facilitator_response_time:
            if block.data["type"] == "encrypted_log" and block.data["edge_hash"] == edge_hash:
                ciphertext = block.data["speed"]
                speed = ts.bfv_vector_from(self.facilitator_ctx, b64_dec(ciphertext))
                speeds += speed
                sqspeeds += speed * speed
                count += 1
            block = block.previous_block
        if count == 0:
            speeds = ts.bfv_vector(self.facilitator_ctx, [self.max_cars * self.max_speed + self.error]
                                   )  # 20_000 is the max speed
            sqspeeds = ts.bfv_vector(self.facilitator_ctx,
                                     [self.max_cars * self.max_speed * self.max_speed + self.error]
                                     )
        return speeds, sqspeeds, count

    def _calculate_neighborhood_encrypted_traffic_data(self):
        traffic = {}
        for edge in tqdm(self.street_graph.edges):
            speeds, sqspeeds, count = self._get_edge_data(edge)
            self.speeds_count_per_street[edge] = count
            traffic[calc_edge_hash(edge)] = (b64_enc(speeds.serialize()), b64_enc(sqspeeds.serialize()))
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
        traffic = self._calculate_neighborhood_encrypted_traffic_data()
        end = datetime.datetime.now()
        self.aggregation_time = end - start
        if not self.quiet:
            print(f"Local node {self.node_id}: Calculated encrypted traffic data in {end - start} seconds")
        traffic_block = {
            "type": "f_a_encrypted" if self.first_node else "f_b_encrypted",
            "traffic": traffic
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
                "a": self.error
            })
        else:
            self.blockchain.add_block({
                "type": "second_node_parameters",
                "b": self.error,
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
    def count_edge_logs(self):
        if len(self.speeds_count_per_street):
            return
        for edge in tqdm(self.street_graph.edges):
            edge_hash = self.street_graph_edges_backward[edge]
            block = self.blockchain.tail
            count = 0
            while block is not None and block.timestamp > self.facilitator_response_time:
                if block.data["type"] == "encrypted_log" and block.data["edge_hash"] == edge_hash:
                    count += 1
                block = block.previous_block
            self.speeds_count_per_street[edge] = count

    def approve_results(self):
        self.update_state()
        if self.state != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
            raise IncorrectStateForAction(self.state, "approve_results")

        self.count_edge_logs()

        decrypted_traffic = {}
        for key, value in tqdm(self.f_a.items()):
            speed, speed_sq = value
            if key not in self.f_b:
                if not self.quiet:
                    print(f'key {key} not in f_b_encrypted')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False
            # for speed
            speed, speed_sq = speed - self.a, speed_sq - self.a
            speed2, speed_sq2 = self.f_b[key]
            speed2, speed_sq2 = speed2 - self.b, speed_sq2 - self.b
            if speed != speed2 or speed_sq != speed_sq2:
                if not self.quiet:
                    print(f'data from node one and two do not match')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False
            n = self.speeds_count_per_street[self.street_graph_edges_forward[key]]
            average = speed / n
            variance = speed_sq - speed * speed / n
            decrypted_traffic[key] = average, variance

        for key, value in tqdm(self.f_b.items()):
            if key not in self.f_a:
                print(f'key {key} not in f_a_encrypted')
                self.blockchain.add_block({
                    "type": "disapproved"
                })
                return False

        self.blockchain.add_block({
            "type": "approved",
            "traffic": decrypted_traffic
        })
        if not self.quiet:
            print(f"Local node {self.node_id}: Results approved.")
        self.decrypted_traffic = decrypted_traffic
        return decrypted_traffic

    # ============== end of step 10 ==============

    def update_facilitator_data(self, block):
        self.facilitator_ctx = ts.context_from(b64_dec(block.data["facilitator_ctx"]))
        self.facilitator_response_time = block.timestamp

    def save_traffic(self, block):
        self.f_a = block.data["f_a"]
        self.f_b = block.data["f_b"]
