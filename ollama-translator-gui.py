import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import queue

from ollama_translator import process_directory, initialize_api_client, lang_dict, API_KEY

class TranslatorGUI:
    def __init__(self, master):
        self.master = master
        master.title("Ollama Translator")
        master.geometry("800x600")

        self.create_widgets()

    def create_widgets(self):
        # Frame for inputs
        input_frame = ttk.Frame(self.master, padding="10")
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Base Language
        ttk.Label(input_frame, text="Base Language:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.base_lang_entry = ttk.Entry(input_frame, width=10)
        self.base_lang_entry.insert(0, "en")
        self.base_lang_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Target Language
        ttk.Label(input_frame, text="Target Language:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.target_lang_entry = ttk.Entry(input_frame, width=10)
        self.target_lang_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        # Input Directory
        ttk.Label(input_frame, text="Input Directory:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.input_dir_entry = ttk.Entry(input_frame, width=50)
        self.input_dir_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(input_frame, text="Browse...", command=self.browse_input_dir).grid(row=1, column=4, padx=5, pady=5)

        # Output Directory
        ttk.Label(input_frame, text="Output Directory:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_dir_entry = ttk.Entry(input_frame, width=50)
        self.output_dir_entry.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(input_frame, text="Browse...", command=self.browse_output_dir).grid(row=2, column=4, padx=5, pady=5)

        # Recursive Checkbox
        self.recursive_var = tk.BooleanVar()
        self.recursive_check = ttk.Checkbutton(input_frame, text="Recursive", variable=self.recursive_var)
        self.recursive_check.grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)

        # Translate Button
        self.translate_button = ttk.Button(self.master, text="Translate", command=self.start_translation)
        self.translate_button.pack(pady=10)

        # Log area
        self.log_area = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, height=20)
        self.log_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.log_area.configure(state='disabled')

    def browse_input_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir_entry.delete(0, tk.END)
            self.input_dir_entry.insert(0, directory)

    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)

    def log(self, message):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, message + '\n')
        self.log_area.configure(state='disabled')
        self.log_area.see(tk.END)

    def start_translation(self):
        self.translate_button.config(state=tk.DISABLED)
        self.log("Starting translation...")

        self.queue = queue.Queue()

        base_lang = self.base_lang_entry.get()
        target_lang = self.target_lang_entry.get()
        input_dir = self.input_dir_entry.get()
        output_dir = self.output_dir_entry.get()
        recursive = self.recursive_var.get()

        if not all([base_lang, target_lang, input_dir]):
            self.log("Error: Base language, target language, and input directory must be specified.")
            self.translate_button.config(state=tk.NORMAL)
            return

        if target_lang not in lang_dict:
            self.log(f"Error: Unsupported target language: {target_lang}")
            self.translate_button.config(state=tk.NORMAL)
            return

        self.thread = threading.Thread(target=self.translation_worker, args=(
            input_dir, output_dir, base_lang, target_lang, recursive, self.queue
        ))
        self.thread.start()
        self.master.after(100, self.process_queue)

    def translation_worker(self, input_dir, output_dir, base_lang, target_lang, recursive, queue):
        client = initialize_api_client(API_KEY)
        process_directory(input_dir, output_dir if output_dir else None, base_lang, target_lang, recursive, client, queue)
        queue.put("DONE")

    def process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg == "DONE":
                    self.log("Translation finished.")
                    self.translate_button.config(state=tk.NORMAL)
                    return
                else:
                    self.log(msg)
        except queue.Empty:
            pass

        if self.thread.is_alive():
            self.master.after(100, self.process_queue)
        else:
            self.log("Translation finished.")
            self.translate_button.config(state=tk.NORMAL)

if __name__ == '__main__':
    root = tk.Tk()
    gui = TranslatorGUI(root)
    root.mainloop()
