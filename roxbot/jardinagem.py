from __future__ import annotations
import os
import re
import time
import cv2
import numpy as np
import pyautogui

class JardinagemBot:
    def __init__(self, *,
                 log,
                 ocr_engine,
                 assets_dir: str,
                 routine_folder: str = "jardinagem",
                 scan_interval: float = 0.05,
                 scales: list[float] | tuple[float, ...] = (0.8, 0.9, 1.0, 1.1, 1.2)):
        self.log = log
        self.ocr_engine = ocr_engine
        self.assets_dir = assets_dir
        self.routine_folder = routine_folder
        self.scan_interval = scan_interval
        self.scales = [s for s in scales if s > 0]

    # --------------- util ---------------
    def _clicar(self, posicao: tuple[int, int]):
        self.log(f"[→] Clicando em {posicao}")
        pyautogui.moveTo(posicao[0], posicao[1], duration=0)
        pyautogui.click()

    def _encontrar_imagem(self, imagem_base: str, thresholds=(0.8, 0.7, 0.67)):
        screenshot = pyautogui.screenshot()
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        base_path = os.path.join(self.assets_dir, self.routine_folder, imagem_base)
        candidates = [base_path]
        name, ext = os.path.splitext(imagem_base)
        for s in self.scales:
            if abs(s - 1.0) < 1e-6:
                continue
            candidates.append(os.path.join(self.assets_dir, self.routine_folder,
                                           f"{name}_scale{int(s*100)}{ext}"))

        for asset_path in candidates:
            template = cv2.imread(asset_path, cv2.IMREAD_COLOR)
            if template is None:
                continue
            h, w = template.shape[:2]
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            for thresh in thresholds:
                if max_val >= thresh:
                    x, y = max_loc[0] + w // 2, max_loc[1] + h // 2
                    self.log(f"[✓] Encontrado '{os.path.basename(asset_path)}' conf {max_val:.2f}")
                    return (x, y), (max_loc, (w, h))
        return None, None

    # --------------- OCR/expressão ---------------
    def _extrair_expressao(self, coord_top_left, size):
        screenshot = pyautogui.screenshot()
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        x, y = coord_top_left
        w, h = size
        roi = screenshot_cv[y:y+h, x:x+w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        eq = cv2.equalizeHist(gray)
        result = self.ocr_engine.ocr(eq, cls=False)
        texto = " ".join([line[1][0] for line in result[0]]) if result and result[0] else ""
        self.log(f"[PaddleOCR] Texto detectado: '{texto}'")
        return self._filtrar_expressao(texto)

    @staticmethod
    def _filtrar_expressao(texto: str) -> str | None:
        matches = re.findall(r"\d+\s*[\+\-\*/]\s*\d+", texto)
        if not matches:
            return None
        return matches[0].replace(" ", "")

    @staticmethod
    def _calcular_expressao(expressao: str) -> str | None:
        try:
            # seguro aqui, pois _filtrar_expressao restringe o padrão
            return str(eval(expressao))
        except Exception:
            return None

    def _preencher_via_teclado_virtual(self, valor: str) -> bool:
        pos_input, _ = self._encontrar_imagem("input_box.png")
        if not pos_input:
            self.log("[!] Campo de input não encontrado.")
            return False
        self._clicar(pos_input)
        for digito in valor:
            pos_tecla, _ = self._encontrar_imagem(f"key_{digito}.png")
            if pos_tecla:
                self._clicar(pos_tecla)
            else:
                self.log(f"[!] Tecla '{digito}' não encontrada.")
        pos_confirma, _ = self._encontrar_imagem("key_confirm.png")
        if pos_confirma:
            self._clicar(pos_confirma)
            return True
        self.log("[!] Botão confirmar não encontrado.")
        return False

    # --------------- loop público ---------------
    def run(self, is_running):
        while is_running():
            espada_data, _ = self._encontrar_imagem("button.png")
            if espada_data:
                self._clicar(espada_data)

            modal_data, meta = self._encontrar_imagem("modal.png")
            if modal_data and meta:
                top_left, size = meta
                expressao = self._extrair_expressao(top_left, size)
                if expressao:
                    resultado = self._calcular_expressao(expressao)
                    if resultado:
                        if self._preencher_via_teclado_virtual(resultado):
                            ok_data, _ = self._encontrar_imagem("ok_button.png")
                            if ok_data:
                                self._clicar(ok_data)
                            else:
                                self.log("[!] Botão OK não encontrado.")
                else:
                    self.log("[!] Nenhuma expressão válida encontrada no OCR.")

            time.sleep(self.scan_interval)
        self.log("[⏹] Jardinagem parada.")


# ──────────────────────────────────────────────────────────────────────
# Assistente de Captura de Assets (Jardinagem) — com captura múltipla para teclas
# ──────────────────────────────────────────────────────────────────────
import cv2 as _cv2
import mss as _mss
import numpy as _np
from typing import Optional

try:
    import tkinter as _tk
    from tkinter import messagebox as _messagebox
    from PIL import Image as _Image, ImageTk as _ImageTk
    _J_TK_OK = True
except Exception:
    _J_TK_OK = False

ASSETS_DIR = "assets"  # usado apenas pelo assistente; o bot em si recebe via construtor
JARDIM_DIR = os.path.join(ASSETS_DIR, "jardinagem")

def _j_ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

class JardinagemAssetWizard(_tk.Toplevel):
    """
    Captura dos assets da Jardinagem.
    Inclui passo 'keys_multi' que recorta key_0..key_9 em uma única captura (cv2.selectROIs).
    """
    STEPS = [
        ("button.png", "Recorte JUSTO do botão que inicia a jardinagem."),
        ("modal.png", "Recorte JUSTO do quadro onde aparece a expressão."),
        ("input_box.png", "Recorte JUSTO da caixa de input numérico."),
        ("key_confirm.png", "Recorte JUSTO do botão CONFIRMAR do teclado virtual."),
        ("keys_multi", "CAPTURA MÚLTIPLA: selecione as teclas numéricas na ordem desejada."),
        ("ok_button.png", "Recorte JUSTO do botão OK/final."),
    ]

    def __init__(self, master: _tk.Misc):
        super().__init__(master)
        self.title("Definir Assets — Jardinagem")
        self.attributes("-topmost", True)
        self.geometry("560x560")
        self.resizable(False, False)
        self.idx = 0
        self.preview_img: Optional[_ImageTk.PhotoImage] = None

        _tk.Label(self, text="", font=("Arial", 12, "bold"), name="lbl").pack(pady=6)
        _tk.Label(self, text="", wraplength=520, justify="left", font=("Arial", 10), name="msg").pack(pady=4)
        self.prev = _tk.Label(self, text="Prévia após capturar.", bd=1, relief="sunken", width=68, height=16)
        self.prev.pack(pady=6)

        row = _tk.Frame(self); row.pack(pady=6)
        _tk.Button(row, text="Capturar", command=self.on_capture, bg="#e2f0ff").grid(row=0, column=0, padx=4)
        _tk.Button(row, text="Pular", command=self.on_skip).grid(row=0, column=1, padx=4)
        _tk.Button(row, text="Avançar", command=self.on_next, bg="#d7ffd7").grid(row=0, column=2, padx=4)

        self.status = _tk.Label(self, text="", fg="gray"); self.status.pack(pady=4)
        self._refresh()

    def _refresh(self) -> None:
        name, hint = self.STEPS[self.idx]
        title = name if name != "keys_multi" else "key_0 .. key_9 (captura múltipla)"
        self.nametowidget("lbl").config(text=f"Passo {self.idx+1}/{len(self.STEPS)}: {title}")
        self.nametowidget("msg").config(text=hint + "\nTudo que você salva vira o tamanho oficial do template.")
        self._update_preview(name)

    def on_capture(self) -> None:
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            shot = _cv2.cvtColor(_np.array(sct.grab(mon)), _cv2.COLOR_BGRA2BGR)

        name, _ = self.STEPS[self.idx]
        if name == "keys_multi":
            self._capture_keys_multi(shot)
            return

        win = "Selecione a ROI e ENTER (ESC cancela)"
        _cv2.namedWindow(win, _cv2.WINDOW_NORMAL); _cv2.resizeWindow(win, 1100, 650)
        x, y, w, h = _cv2.selectROI(win, shot, fromCenter=False, showCrosshair=True)
        _cv2.destroyWindow(win)
        if w <= 0 or h <= 0:
            self.status.config(text="Captura cancelada.", fg="orange")
            return

        crop = shot[y:y+h, x:x+w]
        _j_ensure_dir(JARDIM_DIR)
        out_path = os.path.join(JARDIM_DIR, name)
        _cv2.imwrite(out_path, crop)
        self.status.config(text=f"Salvo {name}", fg="green")
        self._update_preview(name)

    def _capture_keys_multi(self, shot: _np.ndarray) -> None:
        """Seleciona múltiplas ROIs e mapeia a ordem para os dígitos 0..9."""
        win = "Selecione MÚLTIPLAS ROIs (ENTER para concluir, ESC cancela)"
        _cv2.namedWindow(win, _cv2.WINDOW_NORMAL); _cv2.resizeWindow(win, 1100, 650)
        rects = _cv2.selectROIs(win, shot, showCrosshair=True)
        _cv2.destroyWindow(win)

        # Nada selecionado? Informe claramente.
        if rects is None or len(rects) == 0:
            self.status.config(
                text="Nenhuma ROI criada. Dica: clique e ARRASTE para desenhar o retângulo, depois ENTER.",
                fg="orange"
            )
            return

        # Sugestão automática de sequência conforme quantidade de ROIs
        suggested = "0123456789"[:len(rects)]
        if len(rects) == 1:
            suggested = "0"  # caso clássico: pegou só a key_0

        # Caixa para informar a sequência dos dígitos conforme a ordem das seleções:
        popup = _tk.Toplevel(self); popup.title("Ordem das teclas")
        _tk.Label(popup, text=(
            f"Foram selecionadas {len(rects)} ROIs.\n"
            "Digite os dígitos (sem espaços) na ORDEM das seleções:"
        )).pack(padx=10, pady=6)
        seq_var = _tk.StringVar(value=suggested)
        _tk.Entry(popup, textvariable=seq_var, width=24, justify="center").pack(padx=10, pady=6)
        ok = {"clicked": False}
        def _ok(): ok["clicked"] = True; popup.destroy()
        _tk.Button(popup, text="OK", command=_ok).pack(pady=6)
        popup.transient(self); popup.grab_set(); self.wait_window(popup)
        if not ok["clicked"]:
            self.status.config(text="Mapeamento cancelado.", fg="orange"); return

        seq = seq_var.get().strip()
        if any(ch not in "0123456789" for ch in seq):
            self.status.config(text="Sequência contém caracteres inválidos (use somente 0–9).", fg="red"); return
        if len(seq) != len(rects):
            self.status.config(text="Quantidade de dígitos ≠ quantidade de ROIs selecionadas.", fg="red"); return

        _j_ensure_dir(JARDIM_DIR)
        saved = 0
        for (x, y, w, h), digit in zip(rects, seq):
            if w <= 0 or h <= 0:
                continue
            crop = shot[y:y+h, x:x+w]
            out_path = os.path.join(JARDIM_DIR, f"key_{digit}.png")
            _cv2.imwrite(out_path, crop); saved += 1

        self.status.config(text=f"Salvas {saved} teclas (key_*)", fg="green")
        last = os.path.join(JARDIM_DIR, f"key_{seq[-1]}.png")
        self._update_preview(last if os.path.isfile(last) else "keys_multi")

    def on_skip(self) -> None:
        name, _ = self.STEPS[self.idx]
        self.status.config(text=f"Pulado {name}", fg="orange")

    def on_next(self) -> None:
        if self.idx < len(self.STEPS) - 1:
            self.idx += 1; self._refresh()
        else:
            _messagebox.showinfo("OK", "Assets de Jardinagem definidos.")
            self.destroy()

    def _update_preview(self, name: str) -> None:
        p = os.path.join(JARDIM_DIR, name) if name != "keys_multi" else None
        if p and os.path.isfile(p):
            img = _cv2.imread(p, _cv2.IMREAD_COLOR)
            im = _Image.fromarray(_cv2.cvtColor(img, _cv2.COLOR_BGR2RGB)); im.thumbnail((520, 300))
            self.preview_img = _ImageTk.PhotoImage(im)
            self.prev.config(image=self.preview_img, text="")
        else:
            self.prev.config(image="", text="Prévia após capturar.")

def open_asset_wizard_jardinagem(master: Optional[_tk.Misc] = None) -> None:
    if not _J_TK_OK:
        print("[Assistente Jardinagem] Tkinter/PIL indisponível neste ambiente.")
        return
    JardinagemAssetWizard(master or _tk._default_root)
