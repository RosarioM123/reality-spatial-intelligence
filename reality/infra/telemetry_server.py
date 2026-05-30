from flask import Flask, request, jsonify
import numpy as np
import psutil
import time
from queue import Queue
from threading import Thread

from ..core.edge_processor import EdgeFrameProcessor
from ..utils import validate_ingest_payload, measure_latency, record_metrics

app = Flask(__name__)
processor = EdgeFrameProcessor()

ingest_queue = Queue(maxsize=100)

def worker_loop():
    while True:
        item = ingest_queue.get()
        if item is None:
            break
        # Real processing hidden intentionally
        ingest_queue.task_done()

worker = Thread(target=worker_loop, daemon=True)
worker.start()

@app.route("/ingest", methods=["POST"])
def ingest():
    payload = request.json or {}
    ok, error = validate_ingest_payload(payload)
    if not ok:
        return jsonify({"error": error}), 400

    ingest_queue.put({"frame": "placeholder"})

    start = time.time()
    fake_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    graph = processor.process_frame(fake_frame).to_json_rpc()

    latency = measure_latency(start)
    cpu = psutil.cpu_percent(interval=0.05)
    record_metrics(latency, cpu)

    return jsonify({
        "graph": graph,
        "latency_ms": latency,
        "cpu_usage": cpu
    })

if __name__ == "__main__":
    app.run()
