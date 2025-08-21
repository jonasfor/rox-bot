import os
import time
import cv2
import numpy as np
import mss
import pyautogui
pyautogui.FAILSAFE = False  # ⚠️ Desativa o fail-safe


# Controle de execução
_running = False

def set_running(value: bool):
    global _running
    _running = value

def is_running():
    return _running


# ==== CONFIGURATION ====
ASSET_DIR = "assets/missao"
DEBUG_DIR = "debug_matches"
DEBUG_REGIONS_DIR = "debug_regions"
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(DEBUG_REGIONS_DIR, exist_ok=True)

DEBUG_MODE = True  # Toggle region overlay debug
MATCH_THRESHOLD = 0.8
ANALYSIS_INTERVAL = 2  # seconds

# Regions and templates
REGION_PERCENTAGES = {
    "cla_order": (0.68, 0.42, 0.78, 0.64),
    "cla_go": (0.45, 0.77, 0.55, 0.87),
    "cla_go2": (0.3, 0.4, 0.4, 0.5),
    "cla_event": (0.23, 0.12, 0.35, 0.26),
    "cla_send": (0.85, 0.76, 0.98, 0.88),
    "cla_fast_select": (0.6, 0.8, 0.67, 0.9),
    "cla_refresh": (0.15, 0.75, 0.25, 0.9),
    "cla_buy_send": (0.4, 0.8, 0.6, 0.9),
    "mission_panel": (0.0, 0.275, 0.15, 0.6),
    "jump_button": (0.89, 0.03, 0.98, 0.13),
    "auto_play": (0.2, 0.7, 0.3, 0.9),
    "init_mission": (0.8, 0.02, 0.85, 0.15),
    "mission_board": (0.45, 0.49, 0.55, 0.68),
    "mission_go": (0.5, 0.75, 0.6, 0.85),
    "mission_agree": (0.42, 0.8, 0.55, 0.91),
    "action_button": (0.67, 0.62, 0.85, 0.75),
    "action1_button": (0.67, 0.62, 0.85, 0.75),
    "give_button": (0.8, 0.8, 0.86, 0.85),
    "give_button1": (0.78, 0.76, 0.92, 0.95),
    "choose_button": (0.75, 0.3, 0.8, 0.43),
    "choose2_button": (0.74, 0.44, 0.83, 0.65),
    "fast_send_button": (0.4, 0.8, 0.6, 0.9),
    "close_button": (0.9, 0.03, 1, 0.2),
    "miner_button": (0.55, 0.3, 0.65, 0.6),
    "take_picture_button": (0.57, 0.5, 0.67, 0.6),
    "take_shot_button": (0.9, 0.7, 1, 1),
    "close_picture_button": (0.75, 0.12, 0.82, 0.27),
    "close_picture_button2": (0.6, 0.02, 0.67, 0.17),
    "back_picture_button": (0, 0, 0.27, 0.27),
}

REGION_TEMPLATES = {
    # "cla_buy_send": ["cla_buy_send"],
    "mission_panel": ["secondary", "daily", "legendary"],
    "auto_play": ["auto_play"],
    "jump_button": ["jump"],
    "action_button": ["action"],
    "action1_button": ["action1"],
    "give_button": ["give"],
    "give_button1": ["give"],
    "choose_button": ["choose", "search", "search2", "colect"],
    "fast_send_button": ["fast_send"],
    "close_button": ["close"],
    "take_picture_button": ["take_picture", "take_picture2", "take_picture3"],
    "take_shot_button": ["take_shot"],
    "close_picture_button": ["close_picture"],
    "close_picture_button2": ["close2"],
    "back_picture_button": ["back_picture"],
    "choose2_button": ["read"],
    "miner_button": ["miner"],
}

# ==== Load templates ====
def load_templates(folder):
    templates = {}
    for file in os.listdir(folder):
        if file.lower().endswith(".png"):
            name = os.path.splitext(file)[0]
            path = os.path.join(folder, file)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"[⚠️] Failed to load {file}")
                continue
            templates[name] = img
            print(f"[✅] Loaded template: {name} ({img.shape[1]}x{img.shape[0]})")
    if not templates:
        raise FileNotFoundError("No templates found in assets folder.")
    return templates

templates = load_templates(ASSET_DIR)

# ==== Get screen size ====
with mss.mss() as sct:
    monitor = sct.monitors[1]
    SCREEN_WIDTH, SCREEN_HEIGHT = monitor["width"], monitor["height"]
print(f"[🖥️] Screen size: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")

# ==== Convert percentages to pixel coords ====
def get_pixel_regions():
    pixel_regions = {}
    for name, (x1p, y1p, x2p, y2p) in REGION_PERCENTAGES.items():
        x1 = int(x1p * SCREEN_WIDTH)
        y1 = int(y1p * SCREEN_HEIGHT)
        x2 = int(x2p * SCREEN_WIDTH)
        y2 = int(y2p * SCREEN_HEIGHT)
        pixel_regions[name] = (x1, y1, x2, y2)
    return pixel_regions

# ==== Capture a region ====
def capture_region(bbox):
    with mss.mss() as sct:
        monitor = {"left": bbox[0], "top": bbox[1],
                   "width": bbox[2] - bbox[0],
                   "height": bbox[3] - bbox[1]}
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

# ==== Draw region overlay (debug) ====
# ==== Draw region overlay (debug) ====
def draw_region_overlay(regions, frame_idx):
    img = capture_region((0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
    
    for name, (x1, y1, x2, y2) in regions.items():
        # Gera uma cor única para cada região com base no nome
        color = tuple(int(x) for x in np.random.default_rng(seed=hash(name) % (2**32)).integers(0, 256, size=3))
        
        # Desenha o retângulo com a cor única
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, name, (x1 + 5, y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    path = os.path.join(DEBUG_REGIONS_DIR, f"{frame_idx:03}_regions.jpg")
    cv2.imwrite(path, img)
    print(f"[🖼️] Region overlay saved: {path}")

# ==== Match and click ====
def match_and_click(region_name, bbox, frame_idx):
    img = capture_region(bbox)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    found = False

    for tmpl_name in REGION_TEMPLATES.get(region_name, []):
        if tmpl_name not in templates:
            continue
        tmpl = templates[tmpl_name]
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        print(f"[🔍] {tmpl_name} in {region_name}: {max_val:.2f}")

        if max_val >= MATCH_THRESHOLD:
            found = True
            h, w = tmpl.shape
            cx, cy = bbox[0] + max_loc[0] + w // 2, bbox[1] + max_loc[1] + h // 2
            pyautogui.moveTo(cx, cy, duration=0.1)
            pyautogui.click()
            print(f"[🖱] Clicked on {tmpl_name} at ({cx}, {cy})")

            cv2.rectangle(img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            debug_path = os.path.join(DEBUG_DIR, f"{frame_idx:03}_{region_name}_{tmpl_name}.jpg")
            cv2.imwrite(debug_path, img)
            print(f"[💾] Match saved: {debug_path}")

    if not found:
        print(f"[❌] No match found in {region_name}")

# ==== Main loop ====
def start_loop():
    print("[▶️] Loop automático iniciado.")
    frame_idx = 0
    regions = get_pixel_regions()
    last_run = 0

    while is_running():
        now = time.time()
        if now - last_run >= ANALYSIS_INTERVAL:
            print(f"\n[⏱️] Running analysis at {time.strftime('%H:%M:%S')}")
            if DEBUG_MODE:
                print(regions)
                draw_region_overlay(regions, frame_idx)
            for name, bbox in regions.items():
                match_and_click(name, bbox, frame_idx)
            frame_idx += 1
            last_run = now
        time.sleep(0.1)
    
    print("[⏹️] Loop automático encerrado.")

