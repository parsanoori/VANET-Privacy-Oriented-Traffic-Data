from typing import Dict, Tuple
from Blockchain.Blockchain import Blockchain
from Blockchain.BlockchainNode import BlockchainNode
from utils import b64_enc, b64_dec
from enum import Enum
from time import sleep
import datetime
import threading
import tenseal as ts


class GlobalNodeState(Enum):
    IDLE = 0
    WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC = 1
    WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC = 2
    WAITING_FOR_DECRYPTION_REQUEST = 3


class InvalidStateError(Exception):
    def __init__(self, state: GlobalNodeState, action: str):
        self.state = state
        self.action = action
        self.message = f'Cannot perform action {action} while in state {state}'


class GlobalBlockchainNode(BlockchainNode):
    def __init__(self, blockchain: Blockchain, sleep_time: float = 0.2, update_interval: int = 10,
                 quiet=False, poly_modulus_degree=4096, plain_modulus=1032193):
        super().__init__(blockchain)
        self.f_a: Dict[str, Tuple[float, float]] = {}
        self.f_b: Dict[str, Tuple[float, float]] = {}
        self.ts_ctx = ts.context(ts.SCHEME_TYPE.BFV, poly_modulus_degree=poly_modulus_degree,
                                 plain_modulus=plain_modulus)
        self.state = GlobalNodeState.IDLE
        self.current_neighborhood = None
        self.thread = threading.Thread(target=self.run_service)
        self.system_running = True
        self.first_decryption_time = None
        self.second_decryption_time = None
        self.quiet = quiet
        self.decryption_block_size = 0
        self.sleep_time = sleep_time
        self.traffic_update_interval_in_seconds = update_interval

    def run_threaded(self):
        self.thread.start()
        return self.thread

    def get_node_state(self):
        return self.state

    def run_service(self):
        while self.system_running:
            if self.state == GlobalNodeState.IDLE:
                self.facilitator_request()
            elif self.state == GlobalNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
                self.first_traffic_data()
            elif self.state == GlobalNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
                self.second_traffic_data()
            elif self.state == GlobalNodeState.WAITING_FOR_DECRYPTION_REQUEST:
                self.decryption_request()
            else:
                raise InvalidStateError(self.state, "run_server")
            sleep(self.sleep_time)

    def get_latest_block_of_type_for_current_neighborhood(self, block_type: str):
        latest_block = self.blockchain.tail
        while latest_block.data["neighborhood"] != self.current_neighborhood or latest_block.data["type"] != block_type:
            latest_block = latest_block.previous_block
        return latest_block

    def facilitator_request(self):
        if self.state != GlobalNodeState.IDLE:
            raise InvalidStateError(self.state, "check_answer_facilitating_request")
        latest_block = self.blockchain.tail
        if latest_block.data["type"] == "request_facilitator":
            self.blockchain.add_block({
                "type": "facilitator_accepted_request",
                "neighborhood": latest_block.data["neighborhood"],
                "facilitator_ctx": b64_enc(
                    self.ts_ctx.serialize(save_public_key=True, save_secret_key=False, save_galois_keys=False,
                                          save_relin_keys=True)),
            })
            self.state = GlobalNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC
            self.current_neighborhood = latest_block.data["neighborhood"]
            if not self.quiet:
                print(f'global node {self.node_id} accepted request for neighborhood {self.current_neighborhood}')
            return True
        return False

    def get_decryption(self, average_encrypted: Dict[str, Tuple[int, int]]) -> Dict[str, Tuple[int, int]]:
        average_traffic = {}
        for key, value in average_encrypted.items():
            speed, sqspeed = value
            speed = ts.bfv_vector_from(self.ts_ctx, b64_dec(speed)).decrypt()[0]
            sqspeed = ts.bfv_vector_from(self.ts_ctx, b64_dec(sqspeed)).decrypt()[0]
            average_traffic[key] = speed, sqspeed
        return average_traffic

    def decrypt_traffic_data(self, first: bool):
        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False
        checkingType = "f_a_encrypted" if first else "f_b_encrypted"
        if latest_block.data["type"] == checkingType:
            start = datetime.datetime.now()
            if first:
                self.f_a = self.get_decryption(latest_block.data["traffic"])
            else:
                self.f_b = self.get_decryption(latest_block.data["traffic"])
            end = datetime.datetime.now()
            runtime = end - start
            if first:
                self.first_decryption_time = runtime
            else:
                self.second_decryption_time = runtime
            self.state = GlobalNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC if first \
                else GlobalNodeState.WAITING_FOR_DECRYPTION_REQUEST
            if not self.quiet:
                print(f"global node {self.node_id} received {self.node_id}")
            return True
        return False

    def first_traffic_data(self):
        if self.state != GlobalNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForFirstEncryptedAverageTraffic")
        return self.decrypt_traffic_data(True)

    def second_traffic_data(self):
        if self.state != GlobalNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForSecondEncryptedAverageTraffic")
        return self.decrypt_traffic_data(False)

    def decryption_request(self):
        if self.state != GlobalNodeState.WAITING_FOR_DECRYPTION_REQUEST:
            raise InvalidStateError(self.state, "check_and_answer_decryption_request")

        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False

        if latest_block.data["type"] == "send_decryption":
            self.blockchain.add_block({
                "type": "decrypted_data",
                "neighborhood": self.current_neighborhood,
                "f_a": self.f_a,
                "f_b": self.f_b
            })
            self.state = GlobalNodeState.IDLE
            size = len(str(self.blockchain.tail.data))
            self.decryption_block_size = size
            return True
        return False
