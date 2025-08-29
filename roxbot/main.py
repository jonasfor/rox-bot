import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui
import cv2
from paddleocr import PaddleOCR

from jardinagem import JardinagemBot, open_asset_wizard_jardinagem
from pesca import PescaBot, open_asset_wizard  # botão do assistente da Pesca

pyautogui.FAILSAFE = False

ASSETS_DIR = "assets"
ROUTINES = {"Jardinagem": "jardinagem", "Pesca": "pesca"}
SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]

ASSETS_JARDINAGEM = [
    "button.png", "modal.png", "ok_button.png",
    "input_box.png", "key_confirm.png",
    *[f"key_{i}.png" for i in range(10)]
]
ASSETS_PESCA = ["lancar.png", "carretel.png", "carretel_verde.png"]
ROUTINE_ASSETS = {"Jardinagem": ASSETS_JARDINAGEM, "Pesca": ASSETS_PESCA}

SCAN_INTERVAL = 0.05
PESCA_INTERVAL = 0.001  # disponível se quiser aplicar no PescaBot

# ---------------------- UI / Logger ----------------------
root = tk.Tk()
root.title("Auto Solver")
root.attributes("-topmost", True)
root.geometry("250x220")  # janela pequena
root.resizable(False, False)

status_label = tk.Label(root, text="🔴 Parado", fg="red", font=("Arial", 13))
status_label.pack(pady=4)

# Logger apenas no terminal
def log(msg: str):
    print(msg)

# ---------------------- Assets helpers ----------------------
def gerar_assets_escalados():
    for rotina, pasta in ROUTINES.items():
        log(f"🔄 Gerando assets para {rotina}...")
        required_assets = ROUTINE_ASSETS[rotina]
        routine_dir = os.path.join(ASSETS_DIR, pasta)
        for asset in required_assets:
            asset_path = os.path.join(routine_dir, asset)
            if not os.path.isfile(asset_path):
                log(f"[!] Asset '{asset}' não encontrado em {pasta}.")
                continue
            img = cv2.imread(asset_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                log(f"[!] Falha ao ler: {asset_path}")
                continue
            h, w = img.shape[:2]
            for scale in SCALES:
                if abs(scale - 1.0) < 1e-6:
                    continue
                resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                scale_suffix = f"_scale{int(scale*100)}"
                filename, ext = os.path.splitext(asset)
                new_name = f"{filename}{scale_suffix}{ext}"
                new_path = os.path.join(routine_dir, new_name)
                ok = cv2.imwrite(new_path, resized)
                if ok:
                    log(f"[+] Asset gerado: {pasta}/{new_name}")
                else:
                    log(f"[!] Falha ao salvar: {new_path}")
    log("✅ Todos os assets escalados gerados.")

def verificar_assets():
    all_ok = True
    for rotina, pasta in ROUTINES.items():
        log(f"🔎 Verificando assets para {rotina}...")
        required_assets = ROUTINE_ASSETS[rotina]
        routine_dir = os.path.join(ASSETS_DIR, pasta)
        faltando = [asset for asset in required_assets if not os.path.isfile(os.path.join(routine_dir, asset))]
        if faltando:
            log(f"⚠️ Assets faltando em {pasta}:")
            for f in faltando:
                log(f"    ❌ {f}")
            all_ok = False
    if all_ok:
        log("✅ Todos os assets originais presentes.")
    else:
        messagebox.showwarning("Assets Faltando", "Existem assets faltando! Verifique os logs.")
    return all_ok

# ---------------------- Instâncias dos bots ----------------------
ocr_engine = PaddleOCR(use_angle_cls=False, lang='en')

jardinagem_bot = JardinagemBot(
    log=log,
    ocr_engine=ocr_engine,
    assets_dir=ASSETS_DIR,
    routine_folder=ROUTINES["Jardinagem"],
    scan_interval=SCAN_INTERVAL,
    scales=SCALES,
)

pesca_bot = PescaBot(
    log=log,
    assets_dir=ASSETS_DIR,
    routine_folder=ROUTINES["Pesca"],
    scan_interval=SCAN_INTERVAL,  # ou PESCA_INTERVAL se preferir
)

# ---------------------- Controle de execução ----------------------
bot_running = False
selected_routine = tk.StringVar(root, value="Jardinagem")

routine_menu = ttk.Combobox(
    root, textvariable=selected_routine,
    values=list(ROUTINES.keys()), state="readonly", font=("Arial", 10)
)
routine_menu.pack(pady=3)

def is_running():
    return bot_running

def _thread_target():
    if selected_routine.get() == "Jardinagem":
        jardinagem_bot.run(is_running)
    else:
        pesca_bot.run(is_running)

def toggle_bot():
    global bot_running
    if not bot_running:
        if not verificar_assets():
            log("⛔️ Não é possível iniciar o bot sem todos os assets.")
            return
        bot_running = True
        status_label.config(text="🟢 Rodando", fg="green")
        threading.Thread(target=_thread_target, daemon=True).start()
        log(f"[▶️] {selected_routine.get()} iniciada.")
    else:
        bot_running = False
        status_label.config(text="🔴 Parado", fg="red")
        log("[⏹] Bot pausado.")

# Botões
tk.Button(root, text="Iniciar / Parar", command=toggle_bot, bg="lightgray", font=("Arial", 10)).pack(pady=3)
tk.Button(root, text="Gerar Assets Escalados", command=gerar_assets_escalados, bg="lightblue", font=("Arial", 10)).pack(pady=3)
tk.Button(root, text="Assistente de Assets (Jardinagem)", command=lambda: open_asset_wizard_jardinagem(root), bg="#e6ffd6", font=("Arial", 9)).pack(pady=2)
tk.Button(root, text="Assistente de Assets (Pesca)", command=lambda: open_asset_wizard(root), bg="#ffe9b3", font=("Arial", 9)).pack(pady=2)

if not verificar_assets():
    status_label.config(text="⚠️ Assets Incompletos", fg="orange")
else:
    status_label.config(text="🟢 Pronto", fg="green")

root.mainloop()
