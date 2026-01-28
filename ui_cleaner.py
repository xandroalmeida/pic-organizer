import customtkinter as ctk
import sqlite3
import os
import math
from PIL import Image
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# --- CONFIGURATION ---
DB_NAME = "images.db"
DEFAULT_THRESHOLD = 15
ITEMS_PER_PAGE = 50 

# --- DATA MODELS ---
@dataclass
class ImageData:
    id: int
    path: str
    phash: int
    width: int
    height: int
    file_size: int
    capture_date: str

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
        self.conn.execute("PRAGMA journal_mode=WAL;") 

    def get_all_images(self) -> List[ImageData]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, path, phash, width, height, file_size, capture_date FROM images")
            rows = cursor.fetchall()
            return [ImageData(id=r[0], path=r[1], phash=r[2], width=r[3], height=r[4], file_size=r[5], capture_date=r[6]) for r in rows]
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

    # Optimization: Sort by ID or Path doesn't help much with O(N^2), 
    # but printing status helps UX.
    print(f"Recalculating with Threshold {threshold}...")
    
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

        self.title("Duplicate Photo Cleaner (Adjustable Sensitivity)")
        self.geometry("1100x850")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # App State
        self.current_page = 0
        self.total_pages = 0
        self.current_threshold = DEFAULT_THRESHOLD
        self.image_cache = {} 
        self.all_images_cache = [] # Holds all raw data from DB

        # Initialization
        if not os.path.exists(DB_NAME):
            self.show_error("Database not found. Run the indexing script first.")
            return

        self.db = DatabaseHandler(DB_NAME)
        self.all_images_cache = self.db.get_all_images()
        
        # Initial calculation
        self.recalculate_groups()

        if not self.groups:
            self.show_error("No duplicates found initially. Try increasing sensitivity.")
            # Even if empty, we show the UI so user can adjust slider
            self.show_main_list_view()
        else:
            self.show_main_list_view()

    def recalculate_groups(self):
        """Runs the grouping algorithm with current threshold."""
        self.groups = find_duplicate_groups(self.all_images_cache, int(self.current_threshold))
        self.current_page = 0 # Reset to first page
        self.total_pages = math.ceil(len(self.groups) / ITEMS_PER_PAGE)

    def show_error(self, message: str):
        # We only use this for fatal errors, not for empty results anymore (since we have a slider)
        lbl = ctk.CTkLabel(self, text=message, text_color="red", font=("Arial", 20))
        lbl.pack(expand=True)

    def get_cached_thumbnail(self, path: str, size: Tuple[int, int]) -> Optional[ctk.CTkImage]:
        cache_key = f"{path}_{size}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
        try:
            pil_img = Image.open(path)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            if len(self.image_cache) > 1000: self.image_cache.clear() 
            self.image_cache[cache_key] = ctk_img
            return ctk_img
        except Exception:
            return None

    # --- MAIN VIEW ---
    def show_main_list_view(self):
        self.clear_window()

        # --- HEADER AREA (With Slider) ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)
        
        # Title Column
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="Duplicate Groups", font=("Arial", 22, "bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text=f"Total: {len(self.groups)} groups", text_color="gray").pack(anchor="w")

        # Slider Column (Center/Right)
        slider_frame = ctk.CTkFrame(header_frame, fg_color="#2b2b2b", corner_radius=10)
        slider_frame.pack(side="right", padx=20, pady=5)
        
        ctk.CTkLabel(slider_frame, text="Similarity Threshold", font=("Arial", 12, "bold")).pack(pady=(5,0))
        
        self.lbl_threshold = ctk.CTkLabel(slider_frame, text=f"{int(self.current_threshold)}", font=("Arial", 20, "bold"), text_color="#3B8ED0")
        self.lbl_threshold.pack()

        slider = ctk.CTkSlider(
            slider_frame, 
            from_=3, 
            to=20, 
            number_of_steps=17, 
            width=200,
            command=self.on_slider_change
        )
        slider.set(self.current_threshold)
        slider.pack(padx=15, pady=(0, 10))
        
        ctk.CTkLabel(slider_frame, text="(3=Strict, 20=Loose)", font=("Arial", 10), text_color="gray").pack(pady=(0,5))


        # --- LIST CONTENT ---
        # Pagination Info
        page_info = f"Page {self.current_page + 1} of {max(1, self.total_pages)}"
        ctk.CTkLabel(self, text=page_info, text_color="gray").pack(anchor="e", padx=20)

        # Scroll Area
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        if not self.groups:
            ctk.CTkLabel(self.scroll_frame, text="No duplicates found with this threshold.", font=("Arial", 16)).pack(pady=50)
        else:
            # Slicing Logic
            start_index = self.current_page * ITEMS_PER_PAGE
            end_index = start_index + ITEMS_PER_PAGE
            current_batch = self.groups[start_index:end_index]

            for group in current_batch:
                self.create_group_card(group)

        # --- FOOTER ---
        footer = ctk.CTkFrame(self, height=50, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=10)

        btn_prev = ctk.CTkButton(footer, text="< Previous", state="normal" if self.current_page > 0 else "disabled", command=self.prev_page)
        btn_prev.pack(side="left")

        btn_next = ctk.CTkButton(footer, text="Next >", state="normal" if self.current_page < self.total_pages - 1 else "disabled", command=self.next_page)
        btn_next.pack(side="right")

    def on_slider_change(self, value):
        """Callback for slider. Updates label and refreshes list on release."""
        new_val = int(value)
        self.lbl_threshold.configure(text=f"{new_val}")
        
        # Only recalculate if value actually changed (discrete steps)
        if new_val != self.current_threshold:
            self.current_threshold = new_val
            # In a real heavy app, we would debounce this, but for 5000 images it's fast enough
            self.recalculate_groups()
            
            # Refresh view (We call it slightly delayed or directly)
            # Here we just refresh the whole view to show new results
            self.after(100, self.show_main_list_view)


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
        
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text="← Back", width=60, command=self.show_main_list_view).pack(side="left")
        ctk.CTkLabel(top, text="Select to Delete", font=("Arial", 18, "bold")).pack(side="left", padx=20)

        self.grid_frame = ctk.CTkScrollableFrame(self)
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.checkboxes = {}
        cols = 4
        
        for i, img_data in enumerate(group.all_images):
            row, col = divmod(i, cols)
            
            frame = ctk.CTkFrame(self.grid_frame)
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.grid_frame.grid_columnconfigure(col, weight=1)

            thumb = self.get_cached_thumbnail(img_data.path, (250, 250))
            if thumb:
                lbl = ctk.CTkLabel(frame, text="", image=thumb, cursor="hand2")
                lbl.pack(pady=5)
                lbl.bind("<Button-1>", lambda e, p=img_data.path: self.open_zoom(p))

            ctk.CTkButton(frame, text="🔍 Zoom", height=20, fg_color="#444", command=lambda p=img_data.path: self.open_zoom(p)).pack()
            ctk.CTkLabel(frame, text=f"{img_data.path}", font=("Arial", 12)).pack()
            ctk.CTkLabel(frame, text=f"{img_data.width} x {img_data.height}", font=("Arial", 12)).pack()
            ctk.CTkLabel(frame, text=f"{img_data.file_size  / 1024 / 1024:.2f} MB", font=("Arial", 12)).pack()
            ctk.CTkLabel(frame, text=f"{img_data.capture_date}", font=("Arial", 12)).pack()
            chk = ctk.CTkCheckBox(frame, text="Delete", fg_color="red")
            chk.pack(pady=5)
            self.checkboxes[chk] = img_data

        btn_del = ctk.CTkButton(self, text="Delete Selected", fg_color="red", command=lambda: self.delete_selected(group))
        btn_del.pack(pady=10)

    def open_zoom(self, path: str):
        try:
            top = ctk.CTkToplevel(self)
            top.title(f"Viewing: {os.path.basename(path)}")
            top.geometry("900x700")
            top.attributes("-topmost", True)
            top.focus()
            
            pil_img = Image.open(path)
            base_width = 800
            w_percent = (base_width / float(pil_img.size[0]))
            h_size = int((float(pil_img.size[1]) * float(w_percent)))
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
            # Removing from cache list as well to keep counts consistent
            if img in self.all_images_cache:
                self.all_images_cache.remove(img)
            
            if img in group.duplicates: group.duplicates.remove(img)
            if img == group.original and group.duplicates: group.original = group.duplicates.pop(0)
            elif img == group.original: pass 

        if group.total_count <= 1:
            if group in self.groups: self.groups.remove(group)
            self.total_pages = math.ceil(len(self.groups) / ITEMS_PER_PAGE)
            self.show_main_list_view()
        else:
            self.show_detail_view(group)

    def clear_window(self):
        for w in self.winfo_children(): w.destroy()

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()