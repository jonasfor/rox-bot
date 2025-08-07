import time
from auto_bot import (
    capture_region, get_pixel_regions, draw_region_overlay,
    MATCH_THRESHOLD, templates, pyautogui
)
import auto_bot
import threading
import cv2

SEQUENCE_TEMPLATES = {
    "init_mission": ["init_mission"],
    "mission_board": ["mission_board"],
    "mission_go": ["mission_go"],
    "mission_agree": ["mission_agree"],
}

# Espera a imagem aparecer, clica e retorna sucesso
def wait_and_click(region_name, template_names, regions, frame_idx, timeout=120):
    """Tenta encontrar e clicar em uma imagem dentro do timeout"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        success = find_and_click(region_name, template_names, regions, frame_idx)
        if success:
            return True
        time.sleep(0.2)  # pequeno intervalo entre as tentativas
    return False

def find_and_click(region_name, template_names, regions, frame_idx):
    bbox = regions[region_name]
    img = capture_region(bbox)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    for tmpl_name in template_names:
        if tmpl_name not in templates:
            continue
        tmpl = templates[tmpl_name]
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        print(f"[🔍] {tmpl_name} in {region_name}: {max_val:.2f}")
        if max_val >= MATCH_THRESHOLD:
            h, w = tmpl.shape
            cx = bbox[0] + max_loc[0] + w // 2
            cy = bbox[1] + max_loc[1] + h // 2
            pyautogui.moveTo(cx, cy, duration=0.1)
            pyautogui.click()
            print(f"[🖱] Clicked on {tmpl_name} at ({cx}, {cy})")
            return True
    return False

def run_sequence():
    regions = get_pixel_regions()
    frame_idx = 0

    print("[🚀] Iniciando sequência de cliques...")

    steps = [
        ("init_mission", "imagem1"),
        ("mission_board", "imagem2"),
        ("mission_go", "imagem3"),
        ("mission_agree", "imagem4")
    ]

    for step_region, label in steps:
        print(f"[⏳] Aguardando: {label}")
        found = wait_and_click(step_region, SEQUENCE_TEMPLATES[step_region], regions, frame_idx)
        if not found:
            print(f"[❌] Timeout ao aguardar por {label}. Sequência abortada.")
            return
        time.sleep(2)  # Pequeno tempo para permitir transição visual

    print("[✅] Sequência concluída com sucesso. Iniciando auto_bot...")
    auto_bot.set_running(True)
    threading.Thread(target=auto_bot.start_loop, daemon=True).start()
