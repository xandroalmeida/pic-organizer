from typing import Dict, List, Tuple
from model import ImageData

class BKNode:
    def __init__(self, image: ImageData):
        self.image = image
        self.children: Dict[int, BKNode] = {}

class BKTree:
    def __init__(self):
        self.root: BKNode = None

    def add(self, image: ImageData):
        if self.root is None:
            self.root = BKNode(image)
            return

        node = self.root
        while True:
            dist = (node.image.phash ^ image.phash).bit_count()
            
            if dist in node.children:
                node = node.children[dist]
            else:
                node.children[dist] = BKNode(image)
                break

    def search(self, query_image: ImageData, threshold: int) -> List[ImageData]:
        if self.root is None:
            return []

        results = []
        candidates = [self.root]

        while candidates:
            node = candidates.pop()
            
            dist = (node.image.phash ^ query_image.phash).bit_count()

            if dist <= threshold:
                results.append(node.image)

            low = dist - threshold
            high = dist + threshold

            for d, child in node.children.items():
                if low <= d <= high:
                    candidates.append(child)
        
        return results