from dataclasses import dataclass

@dataclass
class ImageData:
    id: int
    path: str
    phash: int
    width: int
    height: int
    file_size: int
    capture_date: str