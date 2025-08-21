import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import sys
import auto_bot
import auto_sequencer  # <- novo

# ==== Redirecionador de log para a interface ====
class TextRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)  # Auto-scroll

    def flush(self):
        pass

# ==== Interface moderna ====
class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RoxBot Interface")
        self.root.geometry("520x460")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)  # Sempre no topo

        self.running = False

        self.build_widgets()

        # Redireciona stdout para a interface
        sys.stdout = TextRedirector(self.log_area)

    def build_widgets(self):
        style_btn = {
            "font": ("Segoe UI", 10, "bold"),
            "bg": "#4CAF50",
            "fg": "#ffffff",
            "activebackground": "#45a049",
            "relief": "flat",
            "bd": 0,
            "width": 20,
            "height": 2,
        }

        # Linha: seleção da sequência
        header = tk.Frame(self.root, bg="#1e1e1e")
        header.pack(fill=tk.X, padx=10, pady=(10, 0))

        tk.Label(header, text="Sequência:", bg="#1e1e1e", fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        self.seq_var = tk.StringVar()
        seqs = auto_sequencer.list_sequences()
        self.seq_combo = ttk.Combobox(header, textvariable=self.seq_var, values=seqs, state="readonly", width=20)
        self.seq_combo.pack(side=tk.LEFT, padx=10)
        if seqs:
            self.seq_combo.current(0)  # seleciona a primeira por padrão

        # Botão: Executar sequência selecionada
        self.seq_btn = tk.Button(
            self.root, text="Executar Sequência", command=self.run_selected_sequence, **style_btn
        )
        self.seq_btn.pack(pady=8)

        # Botão: Iniciar/Parar loop automático
        self.toggle_btn = tk.Button(
            self.root, text="Iniciar AutoBot", command=self.toggle_loop, **style_btn
        )
        self.toggle_btn.pack(pady=8)

        # Área de logs
        self.log_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, height=16, bg="#121212", fg="#ffffff",
            font=("Consolas", 10), insertbackground="white"
        )
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Tema do ttk Combobox mais amigável no escuro (opcional simples)
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure("TCombobox", fieldbackground="#2b2b2b", background="#2b2b2b", foreground="#ffffff")
        style.map('TCombobox', fieldbackground=[('readonly', '#2b2b2b')])

    def toggle_loop(self):
        if not auto_bot.is_running():
            auto_bot.set_running(True)
            threading.Thread(target=auto_bot.start_loop, daemon=True).start()
            self.toggle_btn.config(text="Parar AutoBot", bg="#e53935", activebackground="#d32f2f")
            print("[▶️] AutoBot iniciado.")
        else:
            auto_bot.set_running(False)
            self.toggle_btn.config(text="Iniciar AutoBot", bg="#4CAF50", activebackground="#45a049")
            print("[⏹️] AutoBot parado.")

    def run_selected_sequence(self):
        seq_name = self.seq_var.get().strip()
        if not seq_name:
            print("[⚠️] Selecione uma sequência antes de executar.")
            return
        print(f"[🧭] Executando sequência '{seq_name}'...")
        threading.Thread(target=auto_sequencer.run_sequence, args=(seq_name,), daemon=True).start()

# ==== Iniciar GUI ====
if __name__ == "__main__":
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()
