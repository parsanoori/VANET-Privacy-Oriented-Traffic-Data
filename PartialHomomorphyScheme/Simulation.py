import datetime
import random
import string
from time import sleep
from typing import List, Tuple, Dict

from tqdm import tqdm

from Blockchain import Blockchain
from Blockchain.LocalBlockchain import LocalBlockchain
from PartialHomomorphyScheme.GlobalBlockchainNode import GlobalBlockchainNode, GlobalBlockchainNodeState
from PartialHomomorphyScheme.LocalBlockchainNode import LocalBlockchainNode, NeighborHoodState
import inspect


class Simulation:
    def __init__(self, map_name: str, graph_path: str, quiet: bool, random_speed_log_count: int = 100,
                 sleep_time: float = 0.2,
                 traffic_update_interval_in_seconds: int = 10, sumo_edge_ids: List[Tuple[int, int, string]] = None,
                 key_size: int = 2048):
        self.localBlockChain = LocalBlockchain(map_name)
        self.globalBlockChain = Blockchain.Blockchain()
        self.facilitator = GlobalBlockchainNode(self.globalBlockChain, sleep_time=sleep_time, quiet=quiet,
                                                traffic_update_interval_in_seconds=traffic_update_interval_in_seconds,
                                                key_size=key_size)
        self.localBlockChainNode = LocalBlockchainNode(self.localBlockChain, graph_path, sleep_time=sleep_time,
                                                       traffic_update_interval_in_seconds=traffic_update_interval_in_seconds,
                                                       quiet=quiet)  # local node 0
        self.bridgeLocalToGlobal = LocalBlockchainNode(self.localBlockChain, graph_path, self.globalBlockChain,
                                                       traffic_update_interval_in_seconds=traffic_update_interval_in_seconds,
                                                       quiet=quiet, sleep_time=sleep_time)  # local node 1
        self.secondBridgeLocalToGlobal = LocalBlockchainNode(self.localBlockChain, graph_path,
                                                             self.globalBlockChain,
                                                             sleep_time=sleep_time,
                                                             traffic_update_interval_in_seconds=traffic_update_interval_in_seconds,
                                                             quiet=quiet)  # local node 2
        self.neighborhood_map = self.localBlockChainNode.street_graph
        self.edges = list(self.neighborhood_map.edges)

        self.time_unit = 0.5

        self.threads = []
        self.nodes = [self.facilitator, self.localBlockChainNode, self.bridgeLocalToGlobal,
                      self.secondBridgeLocalToGlobal]

        self.quiet = quiet
        self.random_speed_log_count = random_speed_log_count
        self.sending_traffic_logs_time: datetime.timedelta = None
        self.edge_to_sumo_id: Dict[Tuple[int, int], string] = None
        self.sumo_id_to_edge: Dict[string, Tuple[int, int]] = None
        self.send_traffic_state = False
        if sumo_edge_ids is not None:
            self.add_sumo_edge_ids(sumo_edge_ids)

    def add_sumo_edge_ids(self, sumo_edge_ids):
        self.sumo_id_to_edge = {}
        self.edge_to_sumo_id = {}
        for start, end, id in sumo_edge_ids:
            self.edge_to_sumo_id[(start, end)] = id
            self.sumo_id_to_edge[id] = (start, end)

    def runServers(self):
        for node in self.nodes:
            if hasattr(node, 'run_threaded'):
                result = node.run_threaded()
                self.threads.extend(result if isinstance(result, list) else [result])

    def send_traffic_log(self, edge, speed):
        if self.localBlockChainNode.get_node_state() != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            return
        self.localBlockChainNode.send_encrypted_traffic_log(edge, speed)
        if not self.quiet:
            print(f"Sent traffic log for edge {edge} with speed {speed}")

    def send_sumo_traffic(self, sumo_edge_id, speed):
        edge = self.sumo_id_to_edge[sumo_edge_id]
        self.send_traffic_log(edge, speed)

    def send_random_traffic_log(self):
        if self.send_traffic_state is not True:
            return
        # select a random edge
        edge = random.choice(list(self.edges))
        # edge = self.edges[0]
        # select a random speed
        speed = random.randint(0, 100)
        self.send_traffic_log(edge, speed)

    def send_traffic_random(self):
        start = datetime.datetime.now()
        for _ in tqdm(range(self.random_speed_log_count)):
            if self.localBlockChainNode.get_node_state() == NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
                break
            self.send_random_traffic_log()
        end = datetime.datetime.now()
        self.sending_traffic_logs_time = end - start

        if not self.quiet:
            print(f'localBlockChainNode {self.localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')

    def simulation(self):
        # request facilitator until the answer
        if not self.quiet:
            print(f'facilitator: {self.facilitator.get_node_state()} {inspect.currentframe().f_lineno}')
        if not self.quiet:
            print("Requesting to be a facilitator")
        self.bridgeLocalToGlobal.request_facilitating()
        while self.facilitator.get_node_state() != GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'facilitator: {self.facilitator.get_node_state()} {inspect.currentframe().f_lineno}')
        while self.localBlockChainNode.get_node_state() != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'localBlockChainNode {self.localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')
        while self.secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
            sleep(self.time_unit)
        if not self.quiet:
            print(
                f'secondBridgeLocalToGlobal {self.secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
        # authentication with facilitator completed

        self.send_traffic_state = True
        if self.sumo_id_to_edge is None:
            self.send_traffic_random()
        else:
            print("Now the sumo traffic should be sent by calling the send_sumo_traffic method")

        # wait for traffic update interval to be reached
        self.localBlockChainNode.debug = True
        while self.localBlockChainNode.get_node_state() != NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
            sleep(self.time_unit)

        self.send_traffic_state = False
        if not self.quiet:
            print(f'localBlockChainNode {self.localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')

        # reached the traffic update interval
        # first node to send encrypted average traffic
        if not self.quiet:
            print(f'First node sending encrypted average traffic {inspect.currentframe().f_lineno}')
        self.bridgeLocalToGlobal.add_traffic_to_chains()

        # wait for second node to get updated
        while self.secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FIRST_NODE_AGGREGATED_DATA:
            sleep(self.time_unit)
        if not self.quiet:
            print(
                f'secondBridgeLocalToGlobal {self.secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
        self.secondBridgeLocalToGlobal.add_traffic_to_chains()

        # wait for the first node to get updated
        while self.bridgeLocalToGlobal.get_node_state() != NeighborHoodState.SECOND_NODE_AGGREGATED_DATA:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'bridgeLocalToGlobal {self.bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
        self.bridgeLocalToGlobal.send_parameters()

        # wait for the second node to get updated
        while self.secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FIRST_NODE_PARAMETERS_SENT:
            sleep(self.time_unit)
        if not self.quiet:
            print(
                f'secondBridgeLocalToGlobal {self.secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
        self.secondBridgeLocalToGlobal.send_parameters()

        # wait for the first node to get updated
        while self.bridgeLocalToGlobal.get_node_state() != NeighborHoodState.SECOND_NODE_PARAMETERS_SENT:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'bridgeLocalToGlobal {self.bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

        # sending decryption request
        if not self.quiet:
            print(f"Sending decryption request to facilitator {inspect.currentframe().f_lineno}")
        self.bridgeLocalToGlobal.send_decryption_request()

        # wait for the facilitator to send the decrypted average traffic
        while self.facilitator.get_node_state() != GlobalBlockchainNodeState.IDLE:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'facilitator {self.facilitator.get_node_state()} {inspect.currentframe().f_lineno}')

        # wait for the first node to get updated
        if not self.quiet:
            print(f'bridgeLocalToGlobal {self.bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
        while self.bridgeLocalToGlobal.get_node_state() != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
            sleep(self.time_unit)
        if not self.quiet:
            print(f'bridgeLocalToGlobal {self.bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

        # wait for the second node to get updated
        while self.secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
            sleep(self.time_unit)
        if not self.quiet:
            print(
                f'secondBridgeLocalToGlobal {self.secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

        # approve the decryption
        if not self.quiet:
            print(f'Approving the decryption {inspect.currentframe().f_lineno}')
        self.bridgeLocalToGlobal.approve_results()
        self.bridgeLocalToGlobal.forward_raw_traffic(self.localBlockChain.tail.data)

    def run(self):
        self.runServers()
        self.simulation()
        if not self.quiet:
            print(f'local blockchain block size: {self.bridgeLocalToGlobal.blockchain.get_data_size()}')
        if not self.quiet:
            print(f'global blockchain block size: {self.facilitator.blockchain.get_data_size()}')

    def get_simulation_data(self):
        global_blockchain_size = self.facilitator.blockchain.get_data_size()
        local_blockchain_size = self.bridgeLocalToGlobal.blockchain.get_data_size()
        traffic_log_size = self.localBlockChainNode.traffic_log_size
        traffic_block_size = self.bridgeLocalToGlobal.encrypted_traffic_block_size
        calculating_traffic_log_encryption_time = (
            self.localBlockChainNode.calculating_traffic_log_encryption_time.total_seconds())
        calculating_encrypted_average_time = self.bridgeLocalToGlobal.calculating_encrypted_average_time.total_seconds()
        calculating_decryption_time = self.facilitator.first_decryption_time.total_seconds()
        data = {
            "global_blockchain_size": global_blockchain_size,
            "local_blockchain_size": local_blockchain_size,
            "traffic_log_size": traffic_log_size,
            "traffic_block_size": traffic_block_size,
            "calculating_traffic_log_encryption_time": calculating_traffic_log_encryption_time,
            "calculating_encrypted_average_time": calculating_encrypted_average_time,
            "calculating_decryption_time": calculating_decryption_time,
            "sending_traffic_logs_time": self.sending_traffic_logs_time.total_seconds() if self.sending_traffic_logs_time is not None else None
        }
        return data

    def end_run(self):
        # stop all other threads here
        for n in self.nodes:
            n.system_running = False
        if not self.quiet:
            print(f'after simulation')
