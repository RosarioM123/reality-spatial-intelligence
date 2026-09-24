import time
from typing import Any

import cv2
import numpy as np

from ..config import settings
from .scene_graph import SceneGraph


class EdgeFrameProcessor:
    def __init__(self):
        self.frame_id = 0
        self.detector = cv2.ORB_create(nfeatures=settings.MAX_KEYPOINTS)

    def extract_keypoints(self, frame: np.ndarray) -> list[dict[str, Any]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        keypoints, _ = self.detector.detectAndCompute(gray, None)

        return [
            {"x": int(k.pt[0]), "y": int(k.pt[1]), "size": float(k.size)}
            for k in keypoints
        ]

    def process_frame(self, frame: np.ndarray) -> SceneGraph:
        self.frame_id += 1
        nodes = self.extract_keypoints(frame)
        return SceneGraph(self.frame_id, nodes, timestamp=time.time())
