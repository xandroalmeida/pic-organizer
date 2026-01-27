import customtkinter as ctk
import sqlite3
import os
import math
from PIL import Image
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# --- CONFIGURATION ---
DB_NAME = "images.db"
THRESHOLD = 5
ITEMS_PER_PAGE = 50  # Performance limit (Pagination)

# --- DATA MODELS ---
@dataclass
class ImageData:
    id: int
    path: str
    phash: int

@dataclass
class DuplicateGroup:
    original: ImageData
    duplicates: List[ImageData]

    @property
    def total_count(self) -> int:
        return 1 + len(self.duplicates)
    
    @property
    def all_images(self) -> List[ImageData]:
        return [self.original] + self.duplicates

# --- DATABASE LOGIC ---
class DatabaseHandler:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
        # WAL mode improves concurrency
        self.conn.execute("PRAGMA journal_mode=WAL;") 

    def get_all_images(self) -> List[ImageData]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, path, phash FROM images")
            rows = cursor.fetchall()
            return [ImageData(id=r[0], path=r[1], phash=r[2]) for r in rows]
        except sqlite3.OperationalError:
            return []

    def delete_image(self, image: ImageData) -> None:
        """Removes the image record from DB and deletes the file from disk."""
        self.conn.execute("DELETE FROM images WHERE id = ?", (image.id,))
        self.conn.commit()
        if os.path.exists(image.path):
            try:
                os.remove(image.path)
            except OSError:
                pass

# --- GROUPING LOGIC ---
def find_duplicate_groups(images: List[ImageData], threshold: int) -> List[DuplicateGroup]:
    groups = []
    processed_ids = set()

    print(f"Processing math for {len(images)} images...")
    
    for i in range(len(images)):
        img_a = images[i]
        if img_a.id in processed_ids:
            continue

        current_duplicates = []
        for j in range(i + 1, len(images)):
            img_b = images[j]
            if img_b.id in processed_ids:
                continue

            # Calculate Hamming Distance
            if (img_a.phash ^ img_b.phash).bit_count() <= threshold:
                current_duplicates.append(img_b)
                processed_ids.add(img_b.id)
        
        if current_duplicates:
            groups.append(DuplicateGroup(original=img_a, duplicates=current_duplicates))
            processed_ids.add(img_a.id)

    groups.sort(key=lambda x: x.total_count, reverse=True)
    return groups

# --- GUI APPLICATION ---
class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Duplicate Photo Cleaner (Optimized)")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Pagination State
        self.current_page = 0
        self.total_pages = 0
        self.image_cache = {} # Prevents reloading images from disk constantly

        # Initialization
        if not os.path.exists(DB_NAME):
            self.show_error("Database not found. Run the indexing script first.")
            return

        self.db = DatabaseHandler(DB_NAME)
        all_images = self.db.get_all_images()
        
        # Initial grouping calculation
        self.groups = find_duplicate_groups(all_images, THRESHOLD)

        if not self.groups:
            self.show_error("No duplicates found. Your library is clean.")
            return

        # Calculate pages
        self.total_pages = math.ceil(len(self.groups) / ITEMS_PER_PAGE)
        self.show_main_list_view()

    def show_error(self, message: str):
        lbl = ctk.CTkLabel(self, text=message, text_color="red", font=("Arial", 20))
        lbl.pack(expand=True)

    def get_cached_thumbnail(self, path: str, size: Tuple[int, int]) -> Optional[ctk.CTkImage]:
        """Loads image with caching mechanism to avoid UI freeze."""
        cache_key = f"{path}_{size}"
        
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]

        try:
            pil_img = Image.open(path)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            
            # Simple cache eviction policy if it gets too big
            if len(self.image_cache) > 1000: 
                self.image_cache.clear() 
                
            self.image_cache[cache_key] = ctk_img
            return ctk_img
        except Exception:
            return None

    # --- MAIN VIEW (PAGINATED) ---
    def show_main_list_view(self):
        self.clear_window()

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(header, text=f"Duplicate Groups ({len(self.groups)} total)", font=("Arial", 20, "bold")).pack(side="left")
        
        # Pagination Info
        page_info = f"Page {self.current_page + 1} of {self.total_pages}"
        ctk.CTkLabel(header, text=page_info, text_color="gray").pack(side="right")

        # Scroll Area
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Slicing Logic for Pagination
        start_index = self.current_page * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        current_batch = self.groups[start_index:end_index]

        # Render only current batch
        for group in current_batch:
            self.create_group_card(group)

        # Footer with Navigation
        footer = ctk.CTkFrame(self, height=50, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=10)

        btn_prev = ctk.CTkButton(footer, text="< Previous", state="normal" if self.current_page > 0 else "disabled", command=self.prev_page)
        btn_prev.pack(side="left")

        btn_next = ctk.CTkButton(footer, text="Next >", state="normal" if self.current_page < self.total_pages - 1 else "disabled", command=self.next_page)
        btn_next.pack(side="right")

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.show_main_list_view()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_main_list_view()

    def create_group_card(self, group: DuplicateGroup):
        card = ctk.CTkFrame(self.scroll_frame)
        card.pack(fill="x", pady=5)

        # Thumbnail
        thumb = self.get_cached_thumbnail(group.original.path, (80, 80))
        if thumb:
            ctk.CTkLabel(card, text="", image=thumb).pack(side="left", padx=10, pady=10)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10)
        
        ctk.CTkLabel(info, text=f"Group of {group.total_count} photos", font=("Arial", 16, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=os.path.basename(group.original.path), text_color="gray", anchor="w").pack(fill="x")

        ctk.CTkButton(card, text="Inspect", command=lambda g=group: self.show_detail_view(g)).pack(side="right", padx=20)

    # --- DETAIL VIEW ---
    def show_detail_view(self, group: DuplicateGroup):
        self.clear_window()
        
        # Top Bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text="← Back", width=60, command=self.show_main_list_view).pack(side="left")
        ctk.CTkLabel(top, text="Select to Delete", font=("Arial", 18, "bold")).pack(side="left", padx=20)

        # Scroll Grid
        self.grid_frame = ctk.CTkScrollableFrame(self)
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.checkboxes = {}
        cols = 4
        
        for i, img_data in enumerate(group.all_images):
            row, col = divmod(i, cols)
            
            frame = ctk.CTkFrame(self.grid_frame)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.grid_frame.grid_columnconfigure(col, weight=1)

            # Clickable Thumbnail
            thumb = self.get_cached_thumbnail(img_data.path, (150, 150))
            if thumb:
                lbl = ctk.CTkLabel(frame, text="", image=thumb, cursor="hand2")
                lbl.pack(pady=5)
                lbl.bind("<Button-1>", lambda e, p=img_data.path: self.open_zoom(p))

            # Explicit Zoom Button
            ctk.CTkButton(frame, text="🔍 Zoom", height=20, fg_color="#444", command=lambda p=img_data.path: self.open_zoom(p)).pack()
            
            # Delete Checkbox
            chk = ctk.CTkCheckBox(frame, text="Delete", fg_color="red")
            chk.pack(pady=5)
            self.checkboxes[chk] = img_data

        # Bottom Action Bar
        btn_del = ctk.CTkButton(self, text="Delete Selected", fg_color="red", command=lambda: self.delete_selected(group))
        btn_del.pack(pady=10)

    # --- ZOOM MODAL ---
    def open_zoom(self, path: str):
        try:
            top = ctk.CTkToplevel(self)
            top.title(f"Viewing: {os.path.basename(path)}")
            top.geometry("900x700")
            top.attributes("-topmost", True)
            top.focus()
            
            pil_img = Image.open(path)
            
            # Simple logic to fit image within a reasonable window size
            base_width = 800
            w_percent = (base_width / float(pil_img.size[0]))
            h_size = int((float(pil_img.size[1]) * float(w_percent)))
            
            # If height is too tall, scale by height instead
            if h_size > 600:
                h_size = 600
                w_percent = (h_size / float(pil_img.size[1]))
                base_width = int((float(pil_img.size[0]) * float(w_percent)))

            img = ctk.CTkImage(pil_img, size=(base_width, h_size))
            ctk.CTkLabel(top, text="", image=img).pack(expand=True)
            
        except Exception as e:
            print(f"Error opening zoom: {e}")

    def delete_selected(self, group: DuplicateGroup):
        to_del = [img for chk, img in self.checkboxes.items() if chk.get()]
        if not to_del: return

        for img in to_del:
            self.db.delete_image(img)
            # Update in-memory objects
            if img in group.duplicates: group.duplicates.remove(img)
            if img == group.original and group.duplicates: group.original = group.duplicates.pop(0)
            elif img == group.original: pass # Last item case

        # Logic to decide where to go next
        if group.total_count <= 1:
            if group in self.groups: self.groups.remove(group)
            # Recalculate pages
            self.total_pages = math.ceil(len(self.groups) / ITEMS_PER_PAGE)
            self.show_main_list_view()
        else:
            self.show_detail_view(group)

    def clear_window(self):
        for w in self.winfo_children(): w.destroy()

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()