"""
main.py - запуск программы.

Способы запуска:
  1) Окно с кнопками:                     python main.py
  2) Консоль, только правила:             python main.py договор.docx
  3) Консоль, правила + нейросеть:        python main.py договор.docx --ai
"""

import os
import sys
import threading

from checker import check_contract, format_report, HIGH, MEDIUM, LOW
from reader import read_contract
from ai_helper import explain_with_ai, current_provider, AIUnavailable

AI_TITLE = "РАЗБОР НЕЙРОСЕТИ"


def ai_block(answer: str) -> str:
    """Оформляем ответ нейросети отдельным блоком под отчётом."""
    line = "=" * 60
    return f"\n\n{line}\n{AI_TITLE}\n{line}\n{answer}\n"


def run_console(path: str, use_ai: bool = False) -> None:
    text = read_contract(path)
    findings = check_contract(text)
    print(format_report(findings, os.path.basename(path)))
    if use_ai:
        try:
            print(ai_block(explain_with_ai(text, findings)))
        except AIUnavailable as error:
            print(f"\nНейросеть недоступна: {error}")


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title("Проверка договоров")
    root.geometry("900x650")

    # text и findings нужны, чтобы потом отправить их нейросети
    state = {"report": "", "name": "", "text": "", "findings": []}

    top = tk.Frame(root)
    top.pack(fill="x", padx=10, pady=10)

    summary = tk.Label(top, text="Открой договор (.txt или .docx), и я его проверю",
                       anchor="w", font=("Arial", 11))
    summary.pack(side="left", fill="x", expand=True)

    box = scrolledtext.ScrolledText(root, wrap="word", font=("Consolas", 10))
    box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    box.tag_config("high", foreground="#b00020", font=("Consolas", 10, "bold"))
    box.tag_config("medium", foreground="#b36b00", font=("Consolas", 10, "bold"))
    box.tag_config("low", foreground="#2e7d32", font=("Consolas", 10, "bold"))
    box.tag_config("head", font=("Consolas", 11, "bold"))

    def insert_lines(text: str) -> None:
        for line in text.splitlines():
            tag = None
            if f"[{HIGH}]" in line:
                tag = "high"
            elif f"[{MEDIUM}]" in line:
                tag = "medium"
            elif f"[{LOW}]" in line:
                tag = "low"
            elif line.startswith(("ОТЧЁТ", "Вывод", AI_TITLE)):
                tag = "head"
            box.insert("end", line + "\n", tag)

    def show(report: str) -> None:
        box.config(state="normal")
        box.delete("1.0", "end")
        insert_lines(report)
        box.config(state="disabled")

    def append(text: str) -> None:
        box.config(state="normal")
        insert_lines(text)
        box.see("end")
        box.config(state="disabled")

    def open_file() -> None:
        path = filedialog.askopenfilename(
            title="Выбери договор",
            filetypes=[("Договоры", "*.txt *.docx"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            text = read_contract(path)
        except Exception as error:  # показываем понятную ошибку, а не падаем
            messagebox.showerror("Ошибка", str(error))
            return
        findings = check_contract(text)
        state["name"] = os.path.basename(path)
        state["text"] = text
        state["findings"] = findings
        state["report"] = format_report(findings, state["name"])
        show(state["report"])
        summary.config(text=f"Файл: {state['name']}  |  замечаний: {len(findings)}")

    def ask_ai() -> None:
        if not state["text"]:
            messagebox.showinfo("Нечего проверять", "Сначала открой договор.")
            return
        # Спрашиваем разрешение только если договор уйдёт в интернет.
        # Локальная Ollama работает на этом же компьютере, ничего не отправляя.
        if current_provider() == "claude":
            agree = messagebox.askyesno(
                "Отправить договор нейросети?",
                "Текст договора будет отправлен на сервер нейросети (Anthropic).\n"
                "Не отправляй договоры с секретными или личными данными, если не уверен.\n\n"
                "Продолжить?")
            if not agree:
                return

        ai_button.config(state="disabled")
        summary.config(text="Нейросеть читает договор... на слабом компьютере это может занять несколько минут")

        def work() -> None:
            # Долгую работу делаем в отдельном потоке, чтобы окно не зависало.
            try:
                answer, error = explain_with_ai(state["text"], state["findings"]), None
            except AIUnavailable as exc:
                answer, error = None, str(exc)
            root.after(0, lambda: finish(answer, error))

        def finish(answer, error) -> None:
            ai_button.config(state="normal")
            summary.config(text=f"Файл: {state['name']}  |  замечаний: {len(state['findings'])}")
            if error:
                messagebox.showerror("Нейросеть недоступна", error)
                return
            block = ai_block(answer)
            state["report"] += block
            append(block)

        threading.Thread(target=work, daemon=True).start()

    def save_report() -> None:
        if not state["report"]:
            messagebox.showinfo("Нечего сохранять", "Сначала открой договор.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"Отчёт_{os.path.splitext(state['name'])[0]}.txt",
            filetypes=[("Текстовый файл", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as file:
                file.write(state["report"])
            messagebox.showinfo("Готово", "Отчёт сохранён.")

    tk.Button(top, text="Открыть договор", command=open_file).pack(side="right", padx=(5, 0))
    ai_button = tk.Button(top, text="Спросить нейросеть", command=ask_ai)
    ai_button.pack(side="right", padx=(5, 0))
    tk.Button(top, text="Сохранить отчёт", command=save_report).pack(side="right")

    root.mainloop()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        run_console(args[0], use_ai="--ai" in sys.argv)
    else:
        run_gui()
