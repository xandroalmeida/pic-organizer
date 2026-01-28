import os
import sqlite3
import argparse
import imagehash
import concurrent.futures
from PIL import Image
from tqdm import tqdm
from typing import Optional, Generator, Tuple, List

# --- TYPE ALIASES ---
# Represents the file path and its corresponding 64-bit integer hash
# (path, phash, width, height, file_size, capture_date) 
HashResult = Tuple[str, int, int, int, int, str]

def setup_database(db_name: str = "images.db") -> sqlite3.Connection:
    """
    Initializes the SQLite database with WAL mode for better concurrency.
    Sets 'path' as PRIMARY KEY to automatically handle duplicates.
    """
    conn = sqlite3.connect(db_name)
    
    # Write-Ahead Logging allows simultaneous readers and one writer without locking
    conn.execute("PRAGMA journal_mode=WAL;") 
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            phash INTEGER,
            width INTEGER,
            height INTEGER,
            file_size INTEGER,
            capture_date TEXT
        )
    """)
    conn.commit()
    return conn

def get_capture_date(img: Image.Image, file_path: str) -> str:
    """
    Tries to extract the EXIF DateTimeOriginal. 
    Falls back to File System modification time if EXIF is missing.
    """
    date_str = None
    
    # 1. Try EXIF Data
    try:
        exif = img.getexif()
        if exif:
            # 36867 = DateTimeOriginal
            # 306 = DateTime
            date_str = exif.get(36867) or exif.get(306)
    except Exception:
        pass

    # 2. Fallback to File System (os.path.getmtime)
    if not date_str:
        timestamp = os.path.getmtime(file_path)
        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    return str(date_str)

def compute_phash(file_path: str) -> Optional[HashResult]:
    """
    Worker function: Calculates hash and handles 64-bit signed conversion.
    """
    try:
        with Image.open(file_path) as img:
            image_hash = imagehash.phash(img)
            val = int(str(image_hash), 16)
            if val >= 2**63:
                val -= 2**64
            
            width, height = img.size
            file_size = os.path.getsize(file_path)
            capture_date = get_capture_date(img, file_path)
            return file_path, val, width, height, file_size, capture_date
    except Exception:
        return None

def find_images(root_dir: str) -> Generator[str, None, None]:
    """
    Lazy generator that yields file paths one by one.
    Memory efficient for large directories.
    """
    valid_extensions: set[str] = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
    
    if not os.path.isdir(root_dir):
        raise FileNotFoundError(f"The directory '{root_dir}' does not exist.")

    for root, _, files in os.walk(root_dir):
        for file in files:
            ext: str = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                yield os.path.join(root, file)

def main() -> None:
    # --- ARGUMENT PARSING ---
    parser = argparse.ArgumentParser(description="Index images into SQLite using Perceptual Hashing.")
    parser.add_argument("directory", type=str, help="Root directory to scan for images")
    parser.add_argument("--db", type=str, default="images.db", help="Output database file name")
    parser.add_argument("--batch-size", type=int, default=1000, help="Number of records to commit at once")
    
    args = parser.parse_args()
    
    source_dir: str = args.directory
    db_file: str = args.db
    batch_size: int = args.batch_size

    # --- INITIALIZATION ---
    print(f"[*] Connecting to database: {db_file}")
    conn: sqlite3.Connection = setup_database(db_file)
    cursor: sqlite3.Cursor = conn.cursor()

    print(f"[*] Scanning directory: {source_dir}")
    image_stream: Generator[str, None, None] = find_images(source_dir)

    # --- PROCESSING ---
    print("[*] Starting concurrent hashing and indexing...")
    
    buffer: List[HashResult] = []
    
    # We use ThreadPoolExecutor for I/O bound tasks (reading files)
    # The 'map' function maintains the order of results
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(compute_phash, image_stream)
        
        # tqdm consumes the iterator yielded by executor.map
        for result in tqdm(results, unit=" img"):
            if result is None:
                continue

            buffer.append(result)

            # --- BATCH INSERT STRATEGY ---
            if len(buffer) >= batch_size:
                try:
                    # INSERT OR IGNORE: Skips the row if 'path' already exists
                    cursor.executemany(
                        "INSERT OR IGNORE INTO images (path, phash, width, height, file_size, capture_date) VALUES (?, ?, ?, ?, ?, ?)", 
                        buffer
                    )
                    conn.commit()
                    buffer.clear() # Reset buffer
                except sqlite3.Error as e:
                    print(f"\n[!] Database error: {e}")

    # --- FINAL FLUSH ---
    if buffer:
        cursor.executemany("INSERT OR IGNORE INTO images (path, phash , width, height, file_size, capture_date) VALUES (?, ?, ?, ?, ?, ?)", buffer)
        conn.commit()

    print("\n[*] Indexing complete.")
    conn.close()

if __name__ == "__main__":
    main()