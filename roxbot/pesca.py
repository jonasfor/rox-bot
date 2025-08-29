from __future__ import annotations
import os
import time
import cv2
import mss
import numpy as np
import pyautogui
from typing import Optional

# ==== Assistente de captura de assets (opcional) ====
try:
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image, ImageTk
    _TK_OK = True
except Exception:
    _TK_OK = False

ASSETS_DIR = "assets"
PESCA_DIR = os.path.join(ASSETS_DIR, "pesca")


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


class AssetWizard(tk.Toplevel):
    """Assistente para capturar e salvar os assets da pesca."""
    STEPS = [
        ("lancar.png", "Recorte JUSTO do botão/ícone de Lançar."),
        ("carretel.png", "(Opcional) Recorte do carretel normal/azul."),
        ("carretel_verde.png", "Recorte do MIÚDO VERDE clicável."),
    ]

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Definir Assets — Pesca")
        self.attributes("-topmost", True)
        self.geometry("520x520")
        self.resizable(False, False)
        self.idx = 0
        self.preview_img: Optional[ImageTk.PhotoImage] = None

        tk.Label(self, text="", font=("Arial", 12, "bold"), name="lbl").pack(pady=6)
        tk.Label(self, text="", wraplength=480, justify="left", font=("Arial", 10), name="msg").pack(pady=4)
        self.prev = tk.Label(self, text="Prévia após capturar.", bd=1, relief="sunken", width=60, height=14)
        self.prev.pack(pady=6)

        row = tk.Frame(self)
        row.pack(pady=6)
        tk.Button(row, text="Capturar", command=self.on_capture, bg="#e2f0ff").grid(row=0, column=0, padx=4)
        tk.Button(row, text="Pular", command=self.on_skip).grid(row=0, column=1, padx=4)
        tk.Button(row, text="Avançar", command=self.on_next, bg="#d7ffd7").grid(row=0, column=2, padx=4)

        self.status = tk.Label(self, text="", fg="gray")
        self.status.pack(pady=4)
        self._refresh()

    def _refresh(self) -> None:
        name, hint = self.STEPS[self.idx]
        self.nametowidget("lbl").config(text=f"Passo {self.idx+1}/{len(self.STEPS)}: {name}")
        self.nametowidget("msg").config(text=hint + "\nTudo que você salva vira o tamanho oficial do template.")
        self._update_preview(name)

    def on_capture(self) -> None:
        with mss.mss() as sct:
            mon = sct.monitors[1]
            shot = cv2.cvtColor(np.array(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
        win = "Selecione a ROI e ENTER (ESC cancela)"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 1100, 650)
        x, y, w, h = cv2.selectROI(win, shot, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow(win)
        if w <= 0 or h <= 0:
            self.status.config(text="Captura cancelada.", fg="orange")
            return
        crop = shot[y:y+h, x:x+w]
        name, _ = self.STEPS[self.idx]
        _ensure_dir(PESCA_DIR)
        out_path = os.path.join(PESCA_DIR, name)
        cv2.imwrite(out_path, crop)
        self.status.config(text=f"Salvo {name}", fg="green")
        self._update_preview(name)

    def on_skip(self) -> None:
        name, _ = self.STEPS[self.idx]
        self.status.config(text=f"Pulado {name}", fg="orange")

    def on_next(self) -> None:
        if self.idx < len(self.STEPS) - 1:
            self.idx += 1
            self._refresh()
        else:
            messagebox.showinfo("OK", "Assets definidos.")
            self.destroy()

    def _update_preview(self, name: str) -> None:
        p = os.path.join(PESCA_DIR, name)
        if os.path.isfile(p):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            im.thumbnail((480, 260))
            self.preview_img = ImageTk.PhotoImage(im)
            self.prev.config(image=self.preview_img, text="")
        else:
            self.prev.config(image="", text="Prévia após capturar.")


def open_asset_wizard(master: Optional[tk.Misc] = None) -> None:
    if not _TK_OK:
        print("[Assistente] Tkinter/PIL indisponível neste ambiente.")
        return
    AssetWizard(master or tk._default_root)


class PescaBot:
    def __init__(self, *,
                 log,
                 assets_dir: str,
                 routine_folder: str = "pesca",
                 scan_interval: float = 0.05):
        self.log = log
        self.assets_dir = assets_dir
        self.routine_folder = routine_folder
        self.scan_interval = scan_interval

    def _clicar(self, posicao: tuple[int, int]):
        self.log(f"[→] Clicando em {posicao}")
        pyautogui.moveTo(posicao[0], posicao[1], duration=0)
        pyautogui.click()

    def _encontrar(self, imagem_base: str, region=None, threshold=0.90):
        template_path = os.path.join(self.assets_dir, self.routine_folder, imagem_base)
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            self.log(f"[!] Template não encontrado: {template_path}")
            return None
        t_h, t_w = template.shape[:2]
        with mss.mss() as sct:
            monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]} if region else sct.monitors[1]
            screenshot = np.array(sct.grab(monitor))
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        s_h, s_w = screenshot.shape[:2]
        if s_h < t_h or s_w < t_w:
            self.log(f"[⚠️] ROI muito pequena para '{imagem_base}', usando tela cheia.")
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = np.array(sct.grab(monitor))
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            pos_x, pos_y = max_loc[0] + t_w // 2, max_loc[1] + t_h // 2
            if region:
                pos_x += region[0]
                pos_y += region[1]
            self.log(f"[✓] Encontrado '{imagem_base}' conf {max_val:.2f}")
            return (pos_x, pos_y)
        return None

    def run(self, is_running):
        while is_running():
            lancar_pos = self._encontrar("lancar.png", threshold=0.88)
            if lancar_pos:
                self._clicar(lancar_pos)
                self.log("[🎣] Vara lançada. Aguardando carretel verde...")
                start_time = time.time()
                found_green = False
                roi_size = 400
                carretel_roi = (
                    max(lancar_pos[0] - roi_size // 2, 0),
                    max(lancar_pos[1] - roi_size // 2, 0),
                    roi_size, roi_size
                )
                while is_running() and (time.time() - start_time < 8):
                    verde_pos = self._encontrar("carretel_verde.png", region=carretel_roi, threshold=0.90)
                    if verde_pos:
                        self._clicar(verde_pos)
                        self.log("[✅] Carretel VERDE detectado e clicado!")
                        found_green = True
                        break
                if not found_green:
                    self.log("[!] Timeout: Carretel verde não apareceu.")
            time.sleep(self.scan_interval)
        self.log("[⏹] Pesca parada.")
