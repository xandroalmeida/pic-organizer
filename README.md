# Pic Organizer

A powerful Python tool designed to organize your photo library by detecting and removing duplicate or similar images using **Perceptual Hashing (pHash)** and accurate **Hamming Distance** comparison.

![Badge](https://img.shields.io/badge/Python-3.8%2B-blue)
![Badge](https://img.shields.io/badge/License-MIT-green)
![Badge](https://img.shields.io/badge/Status-Active-success)

## 🌟 Features

- **Smart Detection**: Uses Perceptual Hashing (pHash) to find images that look similar, even if they have different filenames, are resized, or have slight color differences.
- **High Performance**:
    - Multithreaded scanning using `concurrent.futures`.
    - SQLite WAL (Write-Ahead-Logging) mode for fast, concurrent database access.
    - Lazy loading and batch processing for memory efficiency with large libraries.
- **Modern GUI**:
    - Built with **CustomTkinter** for a sleek, dark-mode interface.
    - **Grouped View**: Duplicates are grouped automatically for easy review.
    - **Detail Inspector**: Zoom in, view metadata, and select specific images to keep or delete.
    - **Safe Deletion**: Deletes files both from the database and the filesystem.

## 🛠️ Technologies

- **Python 3.x**
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)**: Modern UI framework.
- **[Pillow](https://python-pillow.org/)**: Image processing.
- **[ImageHash](https://github.com/JohannesBuchner/imagehash)**: Perceptual hashing algorithms.
- **SQLite**: robust local database storage.
- **tqdm**: Progress bars.

## 📦 Installation

1.  **Clone the repository**

    ```bash
    git clone https://github.com/yourusername/pic-organizer.git
    cd pic-organizer
    ```

2.  **Create a virtual environment (Recommended)**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Usage

### 1. Scan and Index Images

Run the scanner to calculate hashes for all images in your directory. This creates an `images.db` database file.

```bash
python scan_dir.py "C:\Users\YourName\Pictures"
```

**Arguments:**

- `directory`: (Required) Path to the folder you want to scan.
- `--db`: Output database filename (default: `images.db`).
- `--batch-size`: Number of records to commit at once (default: `1000`).

### 2. Remove Duplicates

Launch the graphical interface to review and delete found duplicates.

```bash
python ui_cleaner.py
```

**Workflow:**

1.  **Review Groups**: The app lists groups of similar images.
2.  **Inspect**: Click **"Inspecionar"** to view a group in detail.
3.  **Visual Check**: Click images to open a full-size zoom window.
4.  **Select & Delete**: Mark the "Deletar" checkbox for the copies you want to remove and click **"Deletar Selecionados"**.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.
