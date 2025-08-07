import pyautogui
import cv2
import numpy as np
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
from paddleocr import PaddleOCR
import os
import mss
import re

pyautogui.FAILSAFE = False

# OCR Engine
ocr_engine = PaddleOCR(use_angle_cls=False, lang='en')

SCAN_INTERVAL = 0.05  # Jardinagem
PESCA_INTERVAL = 0.001  # Pesca ultrarrápida
DEBUG_MODE = False
bot_running = False
current_routine = "Jardinagem"

ASSETS_DIR = "assets"
ROUTINES = {"Jardinagem": "jardinagem", "Pesca": "pesca"}

SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]

ASSETS_JARDINAGEM = [
    "button.png", "modal.png", "ok_button.png",
    "input_box.png", "key_confirm.png"
] + [f"key_{i}.png" for i in range(10)]
ASSETS_PESCA = ["lancar.png", "carretel.png", "carretel_verde.png"]

ROUTINE_ASSETS = {"Jardinagem": ASSETS_JARDINAGEM, "Pesca": ASSETS_PESCA}

# ---------------------- Logger ----------------------
def log(mensagem):
    log_area.config(state='normal')
    log_area.insert(tk.END, mensagem + "\n")
    log_area.yview(tk.END)
    log_area.config(state='disabled')
    print(mensagem)

# ---------------------- Asset Bootstrap ----------------------
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
            h, w = img.shape[:2]
            for scale in SCALES:
                if scale == 1.0:
                    continue
                resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                scale_suffix = f"_scale{int(scale*100)}"
                filename, ext = os.path.splitext(asset)
                new_name = f"{filename}{scale_suffix}{ext}"
                new_path = os.path.join(routine_dir, new_name)
                cv2.imwrite(new_path, resized)
                log(f"[+] Asset gerado: {pasta}/{new_name}")
    log("✅ Todos os assets escalados gerados.")

# ---------------------- Asset Checker ----------------------
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

# ---------------------- Jardinagem Functions ----------------------
def encontrar_imagem_jardinagem(imagem_base, routine_folder, thresholds=[0.8, 0.7, 0.67]):
    screenshot = pyautogui.screenshot()
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    assets_to_try = [os.path.join(ASSETS_DIR, routine_folder, imagem_base)] + [
        os.path.join(ASSETS_DIR, routine_folder, f"{os.path.splitext(imagem_base)[0]}_scale{int(s*100)}.png")
        for s in SCALES if s != 1.0
    ]
    for asset_path in assets_to_try:
        template = cv2.imread(asset_path, cv2.IMREAD_COLOR)
        if template is None:
            continue
        h, w = template.shape[:2]
        for thresh in thresholds:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= thresh:
                x, y = max_loc[0] + w // 2, max_loc[1] + h // 2
                log(f"[✓] Encontrado '{os.path.basename(asset_path)}' conf {max_val:.2f}")
                return (x, y), (max_loc, (w, h))
    return None, None

def clicar_botao(posicao):
    log(f"[→] Clicando em {posicao}")
    pyautogui.moveTo(posicao[0], posicao[1], duration=0)
    pyautogui.click()

def jardinagem_loop():
    routine_folder = ROUTINES["Jardinagem"]
    while bot_running:
        espada_data, _ = encontrar_imagem_jardinagem("button.png", routine_folder)
        if espada_data:
            clicar_botao(espada_data)
        modal_data, meta = encontrar_imagem_jardinagem("modal.png", routine_folder)
        if modal_data:
            top_left, size = meta
            expressao = extrair_expressao(top_left, size, routine_folder)
            resultado = calcular_expressao(expressao)
            if resultado:
                sucesso = preencher_via_teclado_virtual(resultado, routine_folder)
                if sucesso:
                    ok_data, _ = encontrar_imagem_jardinagem("ok_button.png", routine_folder)
                    if ok_data:
                        clicar_botao(ok_data)
                    else:
                        log("[!] Botão OK não encontrado.")
        time.sleep(SCAN_INTERVAL)
    log("[⏹] Jardinagem parada.")

def extrair_expressao(coord_top_left, size, routine_folder):
    screenshot = pyautogui.screenshot()
    screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    x, y = coord_top_left
    w, h = size
    roi = screenshot_cv[y:y+h, x:x+w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    eq = cv2.equalizeHist(gray)
    result = ocr_engine.ocr(eq, cls=False)
    texto = " ".join([line[1][0] for line in result[0]]) if result[0] else ""
    log(f"[PaddleOCR] Texto detectado: '{texto}'")
    return filtrar_expressao(texto)

def filtrar_expressao(texto):
    matches = re.findall(r"\d+\s*[\+\-\*/]\s*\d+", texto)
    if matches:
        expressao = matches[0].replace(" ", "")
        log(f"[✓] Expressão detectada: '{expressao}'")
        return expressao
    else:
        log("[!] Nenhuma expressão válida encontrada no OCR.")
        return None

def calcular_expressao(expressao):
    try:
        resultado = eval(expressao)
        log(f"[✓] Resultado da expressão '{expressao}' = {resultado}")
        return str(resultado)
    except Exception as e:
        log(f"[!] Erro ao calcular expressão: {e}")
        return None

def preencher_via_teclado_virtual(valor, routine_folder):
    pos_input, _ = encontrar_imagem_jardinagem("input_box.png", routine_folder)
    if not pos_input:
        log("[!] Campo de input não encontrado.")
        return False
    clicar_botao(pos_input)
    for digito in valor:
        tecla_img = f"key_{digito}.png"
        pos_tecla, _ = encontrar_imagem_jardinagem(tecla_img, routine_folder)
        if pos_tecla:
            clicar_botao(pos_tecla)
        else:
            log(f"[!] Tecla '{digito}' não encontrada.")
    pos_confirma, _ = encontrar_imagem_jardinagem("key_confirm.png", routine_folder)
    if pos_confirma:
        clicar_botao(pos_confirma)
        return True
    else:
        log("[!] Botão confirmar não encontrado.")
        return False

# ---------------------- Pesca Functions ----------------------
def encontrar_imagem_pesca(imagem_base, region=None, threshold=0.90):
    template_path = os.path.join(ASSETS_DIR, "pesca", imagem_base)
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        log(f"[!] Template não encontrado: {template_path}")
        return None
    t_h, t_w = template.shape[:2]
    with mss.mss() as sct:
        monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]} if region else sct.monitors[1]
        screenshot = np.array(sct.grab(monitor))
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
    s_h, s_w = screenshot.shape[:2]
    if s_h < t_h or s_w < t_w:
        log(f"[⚠️] ROI muito pequena para '{imagem_base}', usando tela cheia.")
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
        log(f"[✓] Encontrado '{imagem_base}' conf {max_val:.2f}")
        return (pos_x, pos_y)
    return None

def pesca_loop():
    while bot_running:
        lancar_pos = encontrar_imagem_pesca("lancar.png", threshold=0.88)
        if lancar_pos:
            clicar_botao(lancar_pos)
            log("[🎣] Vara lançada. Aguardando carretel verde...")
            start_time = time.time()
            found_green = False
            roi_size = 400
            carretel_roi = (
                max(lancar_pos[0] - roi_size // 2, 0),
                max(lancar_pos[1] - roi_size // 2, 0),
                roi_size, roi_size
            )
            while bot_running and (time.time() - start_time < 8):
                verde_pos = encontrar_imagem_pesca("carretel_verde.png", region=carretel_roi, threshold=0.90)
                if verde_pos:
                    clicar_botao(verde_pos)
                    log("[✅] Carretel VERDE detectado e clicado!")
                    found_green = True
                    break
            if not found_green:
                log("[!] Timeout: Carretel verde não apareceu.")
        time.sleep(SCAN_INTERVAL)
    log("[⏹] Pesca parada.")

# ---------------------- Interface ----------------------
def toggle_bot():
    global bot_running
    if not bot_running:
        if not verificar_assets():
            log("⛔️ Não é possível iniciar o bot sem todos os assets.")
            return
        bot_running = True
        status_label.config(text="🟢 Rodando", fg="green")
        selected_routine = routine_var.get()
        if selected_routine == "Jardinagem":
            threading.Thread(target=jardinagem_loop, daemon=True).start()
        elif selected_routine == "Pesca":
            threading.Thread(target=pesca_loop, daemon=True).start()
        log(f"[▶️] {selected_routine} iniciada.")
    else:
        bot_running = False
        status_label.config(text="🔴 Parado", fg="red")
        log("[⏹] Bot pausado.")

# ---------------------- UI ----------------------
root = tk.Tk()
root.title("Auto Solver")
root.attributes("-topmost", True)
root.geometry("300x300")

status_label = tk.Label(root, text="🔴 Parado", fg="red", font=("Arial", 14))
status_label.pack(pady=10)

routine_var = tk.StringVar(root)
routine_var.set("Jardinagem")
routine_menu = ttk.Combobox(root, textvariable=routine_var, values=list(ROUTINES.keys()), state="readonly", font=("Arial", 12))
routine_menu.pack(pady=5)

start_stop_button = tk.Button(root, text="Iniciar / Parar", command=toggle_bot, bg="lightgray", font=("Arial", 12))
start_stop_button.pack(pady=5)

generate_button = tk.Button(root, text="Gerar Assets Escalados", command=gerar_assets_escalados, bg="lightblue", font=("Arial", 12))
generate_button.pack(pady=5)

log_area = scrolledtext.ScrolledText(root, width=80, height=15, state='disabled', font=("Consolas", 10))
log_area.pack(pady=10)

if not verificar_assets():
    status_label.config(text="⚠️ Assets Incompletos", fg="orange")
else:
    status_label.config(text="🟢 Pronto", fg="green")

root.mainloop()
