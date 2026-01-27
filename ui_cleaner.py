import customtkinter as ctk
import sqlite3
import os
from PIL import Image
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# --- CONFIGURAÇÕES ---
DB_NAME = "images.db"
THRESHOLD = 5

# --- MODELOS DE DADOS ---
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

# --- LÓGICA DE BANCO DE DADOS ---
class DatabaseHandler:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
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
        """Remove do Banco e do Disco"""
        self.conn.execute("DELETE FROM images WHERE id = ?", (image.id,))
        self.conn.commit()
        
        if os.path.exists(image.path):
            try:
                os.remove(image.path)
            except OSError as e:
                print(f"Erro ao deletar arquivo {image.path}: {e}")

# --- LÓGICA DE AGRUPAMENTO ---
def find_duplicate_groups(images: List[ImageData], threshold: int) -> List[DuplicateGroup]:
    groups = []
    processed_ids = set()

    print(f"Analisando {len(images)} imagens em busca de duplicatas...")
    
    for i in range(len(images)):
        img_a = images[i]
        if img_a.id in processed_ids:
            continue

        current_duplicates = []
        
        for j in range(i + 1, len(images)):
            img_b = images[j]
            if img_b.id in processed_ids:
                continue

            # Cálculo de Distância de Hamming
            dist = (img_a.phash ^ img_b.phash).bit_count()

            if dist <= threshold:
                current_duplicates.append(img_b)
                processed_ids.add(img_b.id)
        
        if current_duplicates:
            groups.append(DuplicateGroup(original=img_a, duplicates=current_duplicates))
            processed_ids.add(img_a.id)

    groups.sort(key=lambda x: x.total_count, reverse=True)
    return groups

# --- APLICAÇÃO GUI (CustomTkinter) ---
class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuração da Janela
        self.title("Limpador de Fotos Duplicadas")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Inicialização Lógica
        if not os.path.exists(DB_NAME):
            self.show_error("Banco de dados não encontrado! Rode o script de indexação primeiro.")
            return

        self.db = DatabaseHandler(DB_NAME)
        all_images = self.db.get_all_images()
        self.groups = find_duplicate_groups(all_images, THRESHOLD)

        if not self.groups:
            self.show_error("Nenhuma duplicata encontrada! Sua biblioteca está limpa.")
            return

        # Inicia na Tela Principal
        self.show_main_list_view()

    def show_error(self, message: str):
        lbl = ctk.CTkLabel(self, text=message, text_color="red", font=("Arial", 20))
        lbl.pack(expand=True)

    def load_thumbnail(self, path: str, size: Tuple[int, int]) -> Optional[ctk.CTkImage]:
        """Carrega imagem segura para UI"""
        try:
            pil_img = Image.open(path)
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        except Exception as e:
            print(f"Não foi possível carregar {path}: {e}")
            return None

    # --- NOVO: JANELA DE ZOOM (POPUP) ---
    def open_image_viewer(self, image_path: str):
        """Abre uma janela modal com a imagem grande"""
        try:
            pil_img = Image.open(image_path)
            
            # Cria a janela Pop-up (Toplevel)
            top = ctk.CTkToplevel(self)
            top.title(f"Visualizando: {os.path.basename(image_path)}")
            top.geometry("900x700")
            
            # Força a janela a ficar no topo e receber foco
            top.attributes("-topmost", True)
            top.focus()

            # Lógica para redimensionar mantendo proporção (Fit to Screen)
            screen_w = self.winfo_screenwidth() * 0.8
            screen_h = self.winfo_screenheight() * 0.8
            
            img_w, img_h = pil_img.size
            ratio = min(screen_w/img_w, screen_h/img_h)
            new_size = (int(img_w * ratio), int(img_h * ratio))

            ctk_large = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=new_size)

            # Container da imagem
            lbl = ctk.CTkLabel(top, text="", image=ctk_large)
            lbl.pack(expand=True, fill="both", padx=20, pady=20)
            
            # Botão fechar
            btn_close = ctk.CTkButton(top, text="Fechar", command=top.destroy, fg_color="gray")
            btn_close.pack(pady=10)

        except Exception as e:
            print(f"Erro ao abrir visualizador: {e}")

    # --- TELA 1: LISTA PRINCIPAL ---
    def show_main_list_view(self):
        self.clear_window()

        # Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)
        
        title = ctk.CTkLabel(header_frame, text="Grupos de Duplicatas", font=("Arial", 24, "bold"))
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(header_frame, text=f"{len(self.groups)} grupos encontrados", text_color="gray")
        subtitle.pack(side="left", padx=10, pady=(5,0))

        # Área de Rolagem
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Popular Lista
        for group in self.groups:
            self.create_group_card(group)

    def create_group_card(self, group: DuplicateGroup):
        card = ctk.CTkFrame(self.scroll_frame)
        card.pack(fill="x", pady=5)

        # Thumbnail
        thumb_img = self.load_thumbnail(group.original.path, (80, 80))
        if thumb_img:
            lbl_img = ctk.CTkLabel(card, text="", image=thumb_img)
            lbl_img.pack(side="left", padx=10, pady=10)

        # Texto Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        ctk.CTkLabel(info_frame, text=f"Grupo de {group.total_count} fotos", font=("Arial", 16, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(info_frame, text=os.path.basename(group.original.path), text_color="gray", anchor="w").pack(fill="x")
        ctk.CTkLabel(info_frame, text=os.path.dirname(group.original.path), text_color="gray", font=("Arial", 10), anchor="w").pack(fill="x")

        # Botão Ação
        btn_inspect = ctk.CTkButton(card, text="Inspecionar", command=lambda g=group: self.show_detail_view(g))
        btn_inspect.pack(side="right", padx=20)

    # --- TELA 2: DETALHES ---
    def show_detail_view(self, group: DuplicateGroup):
        self.clear_window()

        # Barra Superior
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=10)

        btn_back = ctk.CTkButton(top_bar, text="← Voltar", width=60, command=self.show_main_list_view)
        btn_back.pack(side="left")

        ctk.CTkLabel(top_bar, text=f"Revisando {group.total_count} Imagens", font=("Arial", 20, "bold")).pack(side="left", padx=20)

        # Grid Rolável
        self.grid_frame = ctk.CTkScrollableFrame(self)
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.checkboxes: Dict[ctk.CTkCheckBox, ImageData] = {}

        # Lógica de Grid
        columns = 4
        row = 0
        col = 0

        for img_data in group.all_images:
            # Container Item
            item_frame = ctk.CTkFrame(self.grid_frame)
            item_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            self.grid_frame.grid_columnconfigure(col, weight=1)

            # Imagem
            ctk_img = self.load_thumbnail(img_data.path, (150, 150))
            if ctk_img:
                # Agora a imagem é clicável para abrir o zoom também
                lbl_pic = ctk.CTkLabel(item_frame, text="", image=ctk_img, cursor="hand2")
                lbl_pic.pack(pady=5)
                # Bind de clique na imagem
                lbl_pic.bind("<Button-1>", lambda e, path=img_data.path: self.open_image_viewer(path))
            
            # Botão de Zoom (Explícito)
            btn_zoom = ctk.CTkButton(
                item_frame, 
                text="🔍 Ver Grande", 
                width=100, 
                height=25,
                fg_color="#444",
                command=lambda path=img_data.path: self.open_image_viewer(path)
            )
            btn_zoom.pack(pady=(0, 5))

            # Nome do Arquivo
            fname = os.path.basename(img_data.path)
            if len(fname) > 20: fname = fname[:17] + "..."
            ctk.CTkLabel(item_frame, text=fname, font=("Arial", 11)).pack()

            # Checkbox Deletar
            chk = ctk.CTkCheckBox(item_frame, text="Deletar", fg_color="red", hover_color="#8b0000")
            chk.pack(pady=5)
            self.checkboxes[chk] = img_data

            # Incremento Grid
            col += 1
            if col >= columns:
                col = 0
                row += 1

        # Barra de Ação Inferior
        action_bar = ctk.CTkFrame(self, height=50)
        action_bar.pack(fill="x", side="bottom")
        
        btn_delete = ctk.CTkButton(
            action_bar, 
            text="Deletar Selecionados", 
            fg_color="red", 
            hover_color="darkred",
            command=lambda: self.delete_selected(group)
        )
        btn_delete.pack(pady=10)

    def delete_selected(self, group: DuplicateGroup):
        deleted_count = 0
        
        to_delete = [img for chk, img in self.checkboxes.items() if chk.get() == 1]

        if not to_delete:
            return 

        for img in to_delete:
            self.db.delete_image(img)
            
            if img in group.duplicates:
                group.duplicates.remove(img)
            if img == group.original:
                if group.duplicates:
                    group.original = group.duplicates.pop(0)
                else:
                    if group in self.groups:
                        self.groups.remove(group)
            
            deleted_count += 1

        print(f"Deletadas {deleted_count} imagens.")

        if group.total_count > 1:
            self.show_detail_view(group)
        else:
            if group in self.groups:
                self.groups.remove(group)
            self.show_main_list_view()

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()