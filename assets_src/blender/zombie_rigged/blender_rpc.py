import json
import socket
import sys


def call(cmd_type, params=None, host="localhost", port=9876, timeout=60):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    payload = json.dumps({"type": cmd_type, "params": params or {}})
    s.sendall(payload.encode("utf-8"))
    chunks = []
    s.settimeout(timeout)
    while True:
        try:
            data = s.recv(65536)
        except socket.timeout:
            break
        if not data:
            break
        chunks.append(data)
        # Heuristic: try to parse what we have; if it parses, we're done.
        try:
            json.loads(b"".join(chunks).decode("utf-8"))
            break
        except Exception:
            continue
    s.close()
    raw = b"".join(chunks).decode("utf-8")
    return json.loads(raw)


def execute_code(code, timeout=60):
    return call("execute_code", {"code": code}, timeout=timeout)


if __name__ == "__main__":
    code = sys.stdin.read()
    result = execute_code(code, timeout=float(sys.argv[1]) if len(sys.argv) > 1 else 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
