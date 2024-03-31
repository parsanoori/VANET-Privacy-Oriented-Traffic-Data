from hashlib import sha256

def calc_edge_hash(edge: tuple) -> str:
    return sha256(str(edge).encode('utf-8')).hexdigest()
