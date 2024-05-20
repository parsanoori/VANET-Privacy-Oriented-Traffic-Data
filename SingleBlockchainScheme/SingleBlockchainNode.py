from Blockchain import Blockchain
from Blockchain.BlockchainNode import BlockchainNode
import datetime
from tqdm import tqdm
import networkx.readwrite.gml as gml
from time import sleep
import threading


class StreetMapAlreadyInBlockchainError(Exception):
    def __init__(self, block_index: int):
        message = "Street map is already in the blockchain at block with index " + str(block_index)
        self.message = message
        super().__init__(self.message)


class SingleBlockchainNode(BlockchainNode):
    def __init__(self, blockchain: Blockchain, neighborhood: str, sleep_time=0.2, traffic_update_interva_in_seconds=10,
                 quiet=False):
        super().__init__(blockchain)
        self.quiet = False
        self.last_update_time = datetime.datetime.now()
        self.latest_average_block = blockchain.head
        self.neighborhood = neighborhood
        self.street_graph = gml.read_gml("./graphs/" + neighborhood + ".gml")
        self.average_traffic_block_size = 0
        self.calculating_sum_time: datetime.timedelta = None
        self.thread = threading.Thread(target=self.run_service)
        self.system_running = True
        self.quiet = quiet
        self.sleep_time = sleep_time
        self.traffic_update_interval_in_seconds = traffic_update_interva_in_seconds

    def run_threaded(self):
        self.thread.start()
        return self.thread

    def run_service(self):
        while self.system_running:
            self.check_average_calculation_time()
            sleep(self.sleep_time)

    def send_traffic_log(self, edge, speed):
        block_to_send = {
            "type": "traffic_speed",
            "speed": speed,
            "edge": edge,
            "neighborhood": self.neighborhood
        }
        self.blockchain.add_block(block_to_send)
        return block_to_send

    def check_average_calculation_time(self):
        if self.last_update_time + datetime.timedelta(
                seconds=self.traffic_update_interval_in_seconds) < datetime.datetime.now():
            self.add_average_traffic_to_blockchain()
            self.last_update_time = datetime.datetime.now()

    def add_street_graph_edges_to_blockchain(self):
        index = 0
        for block in self.blockchain:
            if block.data["type"] == "street_graph":
                raise StreetMapAlreadyInBlockchainError(index)
            index += 1
        street_graph_edges_block = {
            "type": "street_graph",
            "edges": list(self.street_graph_edges_forward.keys()),
        }
        self.last_update_time = datetime.datetime.now()
        self.blockchain.add_block(street_graph_edges_block)
        self.latest_average_block = self.blockchain.tail
        return street_graph_edges_block

    def _get_edge_average_speed(self, edge) -> float:
        block = self.blockchain.tail
        speeds = 0
        count = 0
        while block is not None and block.timestamp > self.last_update_time:
            if (block.data["type"] == "traffic_speed" and block.data["edge"] == edge
                    and block.data["neighborhood"] == self.neighborhood):
                speeds += block.data["speed"]
                count += 1
            block = block.previous_block
        if count == 0:
            return 100
        else:
            raw_average = speeds / count
            return raw_average

    def _calculate_neighborhood_average_traffic(self):
        traffic = {}
        #print("Calculating average traffic for neighborhood " + self.neighborhood + " in node " + str(self.node_id))
        for edge in self.street_graph.edges:
            traffic[edge] = self._get_edge_average_speed(edge)
        return traffic

    def add_average_traffic_to_blockchain(self):
        start = datetime.datetime.now()
        traffic = self._calculate_neighborhood_average_traffic()
        end = datetime.datetime.now()
        self.calculating_sum_time = end - start
        block_to_send = {
            "type": "average_traffic",
            "average_traffic": traffic,
            "neighborhood": self.neighborhood
        }
        self.average_traffic_block_size = len(str(block_to_send))
        self.blockchain.add_block(block_to_send)
        self.latest_average_block = self.blockchain.tail
        self.last_update_time = datetime.datetime.now()
