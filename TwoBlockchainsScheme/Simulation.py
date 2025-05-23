import datetime
from .TwoBlockchainsNode import TwoBlockchainsNode
from Blockchain import Blockchain
import random
from time import sleep
from typing import List, Tuple, Dict
import string


class Simulation:
    def __init__(self, neighborhood: str, quiet: bool, random_speed_log_count: int = 100, sleep_time: float = 0.2,
                 traffic_update_interval_in_seconds: int = 10, sumo_edge_ids = None, gml_file: str = ""):
        if gml_file == "":
            gml_file = './graphs/' + neighborhood + '.gml'
        self.neighborhood = neighborhood
        self.quiet = quiet
        self.localBlockchain = Blockchain.Blockchain()
        self.globalBlockchain = Blockchain.Blockchain()
        self.node = TwoBlockchainsNode(self.localBlockchain, self.globalBlockchain, neighborhood, sleep_time=sleep_time,
                                       traffic_update_interval_in_seconds=traffic_update_interval_in_seconds,
                                       quiet=quiet, gml_file=gml_file)
        self.neighborhood_map = self.node.street_graph
        self.edges = list(self.neighborhood_map.edges)
        self.random_speed_log_count = random_speed_log_count
        self.sending_traffic_logs_time: datetime.timedelta = None
        self.edge_to_sumo_id: Dict[Tuple[int, int], string] = None
        self.sumo_id_to_edge: Dict[string, Tuple[int, int]] = None
        if sumo_edge_ids is not None:
            self.add_sumo_edge_ids(sumo_edge_ids)

    def add_sumo_edge_ids(self, sumo_edge_ids):
        self.sumo_id_to_edge = {}
        self.edge_to_sumo_id = {}
        for start, end, id in sumo_edge_ids:
            self.edge_to_sumo_id[(start, end)] = id
            self.sumo_id_to_edge[id] = (start, end)

    def send_sumo_traffic(self, sumo_edge_id, speed):
        edge = self.sumo_id_to_edge[sumo_edge_id]
        self.node.send_traffic_log(edge, speed)
        if not self.quiet:
            print(f"Sent traffic log for edge {edge} with speed {speed}")


    def send_random_traffic_log(self):
        edge = random.choice(list(self.edges))
        speed = random.randint(0, 100)
        self.node.send_traffic_log(edge, speed)
        if not self.quiet:
            print(f"Sent traffic log for edge {edge} with speed {speed}")

    def simulation(self):
        if not self.quiet:
            print("Starting simulation")

        self.node.add_street_graph_edges_to_blockchain()

        if not self.quiet:
            print("Added street graph edges to blockchain")

        start = datetime.datetime.now()
        for _ in range(self.random_speed_log_count):
            self.send_random_traffic_log()
        end = datetime.datetime.now()
        self.sending_traffic_logs_time = end - start

        if not self.quiet:
            print("Added traffic logs to blockchain\nWaiting for average traffic data to be sent")

        # wait for average traffic data to be sent
        while True:
            if self.localBlockchain.tail.data["type"] == "average_traffic":
                break
            sleep(0.5)

        if not self.quiet:
            print("Received average traffic data")

    def run(self):
        self.node.run_threaded()
        self.simulation()

    def get_simulation_data(self):
        data = {
            "calculating_average_traffic_time": self.node.calculating_sum_time.total_seconds(),
            "average_traffic_block_size": self.node.average_traffic_block_size,
            "local_blockchain_data_size": self.localBlockchain.get_data_size(),
            "global_blockchain_data_sze": self.globalBlockchain.get_data_size(),
            "sending_traffic_logs_time": self.sending_traffic_logs_time.total_seconds(),
            "log_size": self.node.log_size
        }
        return data

    def end_run(self):
        self.node.system_running = False
        self.node.thread.join()
        if not self.quiet:
            print("Simulation ended")


def main():
    simulation = Simulation("nh1", False)
    simulation.run()
    print(simulation.get_simulation_data())
    simulation.end_run()


if __name__ == '__main__':
    main()
