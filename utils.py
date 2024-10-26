from hashlib import sha256

import base64

def b64_enc(data):
    return base64.b64encode(data).decode('utf-8')

def b64_dec(data):
    return base64.b64decode(data)

def calc_edge_hash(edge: tuple) -> str:
    return sha256(str(edge).encode('utf-8')).hexdigest()
