# auto_sequencer.py
import time
import threading
import cv2
import auto_bot
from auto_bot import (
    capture_region, get_pixel_regions,
    MATCH_THRESHOLD, pyautogui
)

# ----------------------------
# REGISTRO DE SEQUÊNCIAS
# ----------------------------
# Cada sequência tem:
# - assets_dir: pasta dos templates (pngs) dessa sequência
# - steps: lista de passos padronizados
#   Campos de cada passo:
#     region: str (região definida em auto_bot.REGION_PERCENTAGES)
#     label: str (texto amigável p/ log)
#     optional: bool (True = tenta 1x e segue se não achar; attempts é ignorado)
#     attempts: int|None (apenas para optional=False; None = loop infinito)
#     templates: Optional[List[str]] (override: nomes de templates a procurar; se ausente -> usa [region])
SEQUENCE_REGISTRY = {
    "missoes": {
        "assets_dir": "assets/missao",
        "steps": [
            {"region": "auto_play",     "label": "imagem0", "optional": True, "attempts": 5},
            {"region": "init_mission",  "label": "imagem1", "optional": False, "attempts": None},
            {"region": "cla_order",     "label": "imagem2", "optional": False, "attempts": None},
            {"region": "cla_go",        "label": "imagem3", "optional": False, "attempts": None},
            {"region": "cla_event",     "label": "imagem4", "optional": False, "attempts": None},
            {"region": "cla_go2",       "label": "imagem5", "optional": False, "attempts": None},
            {"region": "cla_send",      "label": "imagem6", "optional": False, "attempts": None},
            {"region": "cla_fast_select",  "label": "imagem7", "optional": False, "attempts": None},
            {"region": "cla_buy_send",  "label": "imagem8", "optional": False, "attempts": None},
            {"region": "cla_refresh",  "label": "imagem9", "optional": False, "attempts": None},
            {"region": "init_mission",  "label": "imagem10", "optional": False, "attempts": None},
            {"region": "mission_board", "label": "imagem11", "optional": False,  "attempts": None},  # attempts ignorado
            {"region": "mission_go",    "label": "imagem12", "optional": False, "attempts": None},
            {"region": "mission_agree", "label": "imagem13", "optional": False, "attempts": None},
        ],
    },

    # Exemplo extra (só como modelo; ajuste regiões/nomes/templates/pastas se quiser usar)
    "mineracao": {
        "assets_dir": "assets/mineracao",
        "steps": [
            {"region": "miner_button",      "label": "abrir_minerador", "optional": False, "attempts": None},
            {"region": "take_picture_button","label": "tirar_foto",     "optional": True,  "attempts": 2, "templates": ["take_picture", "take_picture2", "take_picture3"]},
            {"region": "take_shot_button",  "label": "confirmar_foto",  "optional": False, "attempts": 5},
            {"region": "close_picture_button","label": "fechar_foto",   "optional": True,  "attempts": 1},
        ],
    },
}

# ----------------------------
# CORE DA EXECUÇÃO
# ----------------------------

def _find_and_click(region_name, template_names, regions):
    bbox = regions[region_name]
    img = capture_region(bbox)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    for tmpl_name in template_names:
        tmpl = auto_bot.templates.get(tmpl_name)
        if tmpl is None:
            continue
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


def _wait_and_click(region_name, template_names, regions, optional=False, attempts=None, sleep_between=0.2):
    """
    Regras:
      - optional=True -> attempts é ignorado; tenta 1 vez; se falhar, segue o fluxo.
      - optional=False:
          * attempts=None -> tenta infinitamente até encontrar
          * attempts=N    -> tenta N vezes; se falhar, aborta sequência
    """
    if optional:
        success = _find_and_click(region_name, template_names, regions)
        if not success:
            print(f"[➡️] Passo opcional '{region_name}' não encontrado (1 tentativa).")
        return success

    # Obrigatório
    if attempts is None:
        # loop infinito
        while True:
            if _find_and_click(region_name, template_names, regions):
                return True
            time.sleep(sleep_between)
    else:
        for i in range(1, attempts + 1):
            if _find_and_click(region_name, template_names, regions):
                return True
            print(f"[↻] Tentativa obrigatória {i}/{attempts} falhou para '{region_name}'")
            time.sleep(sleep_between)
        return False


def run_sequence(sequence_name: str):
    """
    Executa a sequência pelo nome presente no SEQUENCE_REGISTRY.
    Ao concluir a sequência com sucesso, inicia o loop do auto_bot.
    """
    seq = SEQUENCE_REGISTRY.get(sequence_name)
    if not seq:
        print(f"[❌] Sequência '{sequence_name}' não encontrada.")
        return

    assets_dir = seq["assets_dir"]
    steps = seq["steps"]

    # Carrega templates específicos da sequência
    try:
        auto_bot.templates = auto_bot.load_templates(assets_dir)
        print(f"[✅] Templates carregados para '{sequence_name}' a partir de '{assets_dir}'.")
    except Exception as e:
        print(f"[❌] Erro ao carregar templates da sequência '{sequence_name}': {e}")
        return

    regions = get_pixel_regions()
    print(f"[🚀] Iniciando sequência '{sequence_name}'...")

    for step in steps:
        region = step["region"]
        label = step.get("label", region)
        optional = bool(step.get("optional", False))
        attempts = step.get("attempts", None)

        # Se o passo forneceu 'templates', usa-os; senão, procura pelo nome da região
        template_names = step.get("templates") or [region]

        print(f"[⏳] Aguardando: {label} ({'opcional' if optional else 'obrigatório'})")

        found = _wait_and_click(
            region_name=region,
            template_names=template_names,
            regions=regions,
            optional=optional,
            attempts=attempts
        )

        if not found and not optional:
            print(f"[❌] Passo obrigatório '{label}' não foi encontrado. Sequência abortada.")
            return

        time.sleep(2)  # tempo para transições visuais

    print("[✅] Sequência concluída com sucesso. Iniciando auto_bot...")
    auto_bot.set_running(True)
    threading.Thread(target=auto_bot.start_loop, daemon=True).start()


def list_sequences():
    """Retorna a lista de nomes de sequências registradas."""
    return list(SEQUENCE_REGISTRY.keys())
