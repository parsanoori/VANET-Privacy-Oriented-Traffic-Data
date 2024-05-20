import datetime

from .SingleBlockchainNode import SingleBlockchainNode
from Blockchain import Blockchain
import random
from time import sleep


class Simulation:
    def __init__(self, neighborhood: str, quiet: bool, random_speed_log_count: int = 100, sleep_time: float = 0.2,
                 traffic_update_interval_in_seconds: int = 10):
        self.blockchain = Blockchain.Blockchain()
        self.node = SingleBlockchainNode(self.blockchain, neighborhood, sleep_time=sleep_time,
                                         traffic_update_interva_in_seconds=traffic_update_interval_in_seconds,
                                         quiet=quiet)
        self.neighborhood = neighborhood
        self.quiet = quiet
        self.neighborhood_map = self.node.street_graph
        self.edges = list(self.neighborhood_map.edges)
        self.random_speed_log_count = random_speed_log_count
        self.sending_traffic_logs_time: datetime.timedelta = None

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
            if self.blockchain.tail.data["neighborhood"] != self.neighborhood:
                if not self.quiet:
                    print(
                        f"neighborhood not matching\tself.blockchain.tail.data[\"neighborhood\"] = {self.blockchain.tail.data['neighborhood']}\tself.neighborhood = {self.neighborhood}")
            else:
                if self.blockchain.tail.data["type"] == "average_traffic":
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
            "blockchain_data_size": self.blockchain.get_data_size(),
            "sending_traffic_logs_time": self.sending_traffic_logs_time.total_seconds(),
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
    simulation.end_run()


if __name__ == '__main__':
    main()
