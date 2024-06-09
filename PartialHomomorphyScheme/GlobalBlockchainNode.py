from typing import Dict, Tuple
from Blockchain.Blockchain import Blockchain
from Blockchain.BlockchainNode import BlockchainNode
from phe import paillier
from enum import Enum
from time import sleep
import datetime
import threading


class GlobalBlockchainNodeState(Enum):
    IDLE = 0
    WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC = 1
    WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC = 2
    WAITING_FOR_DECRYPTION_REQUEST = 3


class InvalidStateError(Exception):
    def __init__(self, state: GlobalBlockchainNodeState, action: str):
        self.state = state
        self.action = action
        self.message = f'Cannot perform action {action} while in state {state}'


class GlobalBlockchainNode(BlockchainNode):
    def __init__(self, blockchain: Blockchain, sleep_time: float = 0.2, traffic_update_interval_in_seconds: int = 10,
                 quiet=False):
        super().__init__(blockchain)
        self.f_ab_decrypted_average_traffic: Dict[str, float] = {}
        self.f_cd_decrypted_average_traffic: Dict[str, float] = {}
        self.key_pair = paillier.generate_paillier_keypair()
        self.state = GlobalBlockchainNodeState.IDLE
        self.current_neighborhood = None
        self.thread = threading.Thread(target=self.run_service)
        self.system_running = True
        self.first_decryption_time = None
        self.second_decryption_time = None
        self.quiet = quiet
        self.decryption_block_size = 0
        self.sleep_time = sleep_time
        self.traffic_update_interval_in_seconds = traffic_update_interval_in_seconds

    def run_threaded(self):
        self.thread.start()
        return self.thread

    def get_node_state(self):
        return self.state

    def run_service(self):
        while self.system_running:
            if self.state == GlobalBlockchainNodeState.IDLE:
                self.check_and_answer_facilitating_request()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
                self.check_for_first_encrypted_average_traffic()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
                self.check_for_second_encrypted_average_traffic()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST:
                self.check_and_answer_decryption_request()
            else:
                raise InvalidStateError(self.state, "run_server")
            sleep(self.sleep_time)

    def get_latest_block_of_type_for_current_neighborhood(self, block_type: str):
        latest_block = self.blockchain.tail
        while latest_block.data["neighborhood"] != self.current_neighborhood or latest_block.data["type"] != block_type:
            latest_block = latest_block.previous_block
        return latest_block

    def check_and_answer_facilitating_request(self):
        if self.state != GlobalBlockchainNodeState.IDLE:
            raise InvalidStateError(self.state, "check_answer_facilitating_request")
        latest_block = self.blockchain.tail
        if latest_block.data["type"] == "request_facilitator":
            self.blockchain.add_block({
                "type": "facilitator_accepted_request",
                "neighborhood": latest_block.data["neighborhood"],
                "public_key": str(self.key_pair[0].n)
            })
            self.state = GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC
            self.current_neighborhood = latest_block.data["neighborhood"]
            if not self.quiet:
                print(f'global node {self.node_id} accepted request for neighborhood {self.current_neighborhood}')
            return True
        return False

    def get_decryption(self, average_encrypted: Dict[str, Tuple[int, int]]) -> Dict[str, int]:
        average_traffic = {}
        for key, value in average_encrypted.items():
            ciphertext, exponent = value
            public_key = self.key_pair[0]
            encrypted_speed = paillier.EncryptedNumber(public_key, ciphertext, exponent)
            average_traffic[key] = self.key_pair[1].decrypt(encrypted_speed)
        return average_traffic

    def calculate_average_traffic_decryption(self, first: bool):
        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False
        checkingType = "f_ab_encrypted_average_traffic" if first else "f_cd_encrypted_average_traffic"
        if latest_block.data["type"] == checkingType:
            start = datetime.datetime.now()
            if first:
                self.f_ab_decrypted_average_traffic = self.get_decryption(latest_block.data["average_traffic"])
            else:
                self.f_cd_decrypted_average_traffic = self.get_decryption(latest_block.data["average_traffic"])
            end = datetime.datetime.now()
            runtime = end - start
            if first:
                self.first_decryption_time = runtime
            else:
                self.second_decryption_time = runtime
            self.state = GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC if first \
                else GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST
            if not self.quiet:
                print(f"global node {self.node_id} received {self.node_id}")
            return True
        return False

    def check_for_first_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForFirstEncryptedAverageTraffic")
        return self.calculate_average_traffic_decryption(True)

    def check_for_second_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForSecondEncryptedAverageTraffic")
        return self.calculate_average_traffic_decryption(False)

    def check_and_answer_decryption_request(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST:
            raise InvalidStateError(self.state, "check_and_answer_decryption_request")

        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False

        if latest_block.data["type"] == "send_decryption":
            self.blockchain.add_block({
                "type": "decrypted_average_traffic",
                "neighborhood": self.current_neighborhood,
                "f_ab_decrypted_average_traffic": self.f_ab_decrypted_average_traffic,
                "f_cd_decrypted_average_traffic": self.f_cd_decrypted_average_traffic
            })
            self.state = GlobalBlockchainNodeState.IDLE
            size = len(str(self.blockchain.tail.data))
            self.decryption_block_size = size
            return True
        return False
