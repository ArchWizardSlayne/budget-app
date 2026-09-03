#!/usr/bin/env python3
"""Neon Budget Tracker — Modern GUI built with CustomTkinter."""

import json
import os
import tkinter as tk
from tkinter import colorchooser
from pathlib import Path

import customtkinter as ctk

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG = "#1a1a2e"
BG_FRAME = "#16213e"
BG_ENTRY = "#0f3460"
NEON_GREEN = "#00ff41"
NEON_RED = "#ff0040"
FG = "#e0e0e0"
FG_DIM = "#8892a0"

DEFAULT_TOTAL = 2000
DEFAULT_CATEGORIES = [
    {"name": "Rent", "percent": 0, "color": "#ff00ff"},
    {"name": "Food", "percent": 0, "color": "#00ffff"},
    {"name": "Transport", "percent": 0, "color": "#ffff00"},
    {"name": "Fun", "percent": 0, "color": "#ff6600"},
    {"name": "Savings", "percent": 0, "color": "#00ff41"},
]

SAVE_PATH = Path(__file__).parent / "budget.json"


# ── App ──────────────────────────────────────────────────────────────────────
class BudgetApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Budget Tracker")
        self.geometry("920x720")
        self.configure(fg_color=BG)
        self.minsize(780, 620)

        self.resizable(True, True)
        self.total = tk.IntVar(value=DEFAULT_TOTAL)
        self.locked = tk.BooleanVar(value=True)
        self.categories: list[dict] = []
        self.sliders: list[ctk.CTkSlider] = []
        self.percent_labels: list[ctk.CTkLabel] = []
        self.dollar_labels: list[ctk.CTkLabel] = []
        self.swatches: list[ctk.CTkButton] = []

        self._build_top()
        self._build_categories()
        self._build_footer()
        self._load()

    # ── Top: Total Budget ────────────────────────────────────────────────
    def _build_top(self):
        frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)
        frame.pack(fill="x", padx=24, pady=(24, 12))

        ctk.CTkLabel(
            frame, text="TOTAL BUDGET", font=("Segoe UI", 14, "bold"),
            text_color=FG_DIM
        ).pack(side="left", padx=(20, 8), pady=18)

        self.total_entry = ctk.CTkEntry(
            frame, textvariable=self.total, width=160, height=44,
            font=("Consolas", 26, "bold"), fg_color=BG_ENTRY,
            text_color=NEON_GREEN, border_color=NEON_GREEN,
            border_width=2, corner_radius=10, justify="center",
            state="disabled",
        )
        self.total_entry.pack(side="left", padx=4, pady=18)

        ctk.CTkLabel(
            frame, text="$", font=("Consolas", 26, "bold"),
            text_color=NEON_GREEN
        ).pack(side="left", padx=(0, 8), pady=18)

        self.lock_btn = ctk.CTkButton(
            frame, text="🔒", width=44, height=44, corner_radius=10,
            font=("Segoe UI", 20), fg_color=BG_ENTRY,
            hover_color="#1a3a6a", command=self._toggle_lock,
        )
        self.lock_btn.pack(side="left", padx=(12, 20), pady=18)

    def _toggle_lock(self):
        new = not self.locked.get()
        self.locked.set(new)
        if new:
            self.total_entry.configure(state="disabled")
            self.lock_btn.configure(text="🔒")
        else:
            self.total_entry.configure(state="normal")
            self.lock_btn.configure(text="🔓")
            self.total_entry.focus_set()

    # ── Categories ───────────────────────────────────────────────────────
    def _build_categories(self):
        self.cat_frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)
        self.cat_frame.pack(fill="both", expand=True, padx=24, pady=12)
        self.cat_frame.columnconfigure(0, weight=0)
        self.cat_frame.columnconfigure(1, weight=0)
        self.cat_frame.columnconfigure(2, weight=1)
        self.cat_frame.columnconfigure(3, weight=0)
        self.cat_frame.columnconfigure(4, weight=0)

        ctk.CTkLabel(
            self.cat_frame, text="CATEGORIES", font=("Segoe UI", 12, "bold"),
            text_color=FG_DIM
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=20, pady=(16, 4))

        for i, cat in enumerate(DEFAULT_CATEGORIES):
            self._add_category_row(i + 1, cat)

    def _add_category_row(self, row: int, cat: dict):
        color = cat["color"]
        pct = cat["percent"]
        name = cat["name"]

        # color swatch (clickable)
        swatch = ctk.CTkButton(
            self.cat_frame, text="", width=28, height=28,
            fg_color=color, hover_color=color, corner_radius=8,
            border_width=2, border_color="#ffffff",
            command=lambda idx=row - 1: self._pick_color(idx),
        )
        swatch.grid(row=row, column=0, padx=(20, 10), pady=10, sticky="w")
        self.swatches.append(swatch)

        # category name
        ctk.CTkLabel(
            self.cat_frame, text=name, font=("Segoe UI", 17, "bold"),
            text_color=color, width=120, anchor="w",
        ).grid(row=row, column=1, padx=(0, 10), pady=10, sticky="w")

        # slider
        slider = ctk.CTkSlider(
            self.cat_frame, from_=0, to=100, number_of_steps=100,
            width=320, height=24, corner_radius=12,
            fg_color="#2a2a4a", progress_color=color,
            button_color=color, button_hover_color=color,
            command=lambda val, idx=row - 1: self._on_slider(idx, val),
        )
        slider.set(pct)
        slider.grid(row=row, column=2, padx=10, pady=10, sticky="ew")
        self.sliders.append(slider)

        # percent label
        pct_lbl = ctk.CTkLabel(
            self.cat_frame, text=f"{pct}%", font=("Consolas", 16, "bold"),
            text_color=FG, width=56, anchor="e",
        )
        pct_lbl.grid(row=row, column=3, padx=(4, 8), pady=10)
        self.percent_labels.append(pct_lbl)

        # dollar label
        dollar = self._calc_dollar(pct)
        dol_lbl = ctk.CTkLabel(
            self.cat_frame, text=f"${dollar:,.0f}",
            font=("Consolas", 16, "bold"), text_color=color,
            width=90, anchor="e",
        )
        dol_lbl.grid(row=row, column=4, padx=(0, 20), pady=10, sticky="e")
        self.dollar_labels.append(dol_lbl)

        self.categories.append({"name": name, "percent": pct, "color": color})

    def _pick_color(self, idx: int):
        current = self.categories[idx]["color"]
        result = colorchooser.askcolor(
            initialcolor=current, title=f"Pick color for {self.categories[idx]['name']}"
        )
        if result and result[1]:
            hex_color = result[1]
            self.categories[idx]["color"] = hex_color
            self.swatches[idx].configure(fg_color=hex_color, hover_color=hex_color)
            self.dollar_labels[idx].configure(text_color=hex_color)
            # update slider colors
            self.sliders[idx].configure(
                progress_color=hex_color,
                button_color=hex_color,
                button_hover_color=hex_color,
            )
            # update category name color
            for widget in self.cat_frame.winfo_children():
                info = widget.grid_info()
                if info.get("row") == idx + 1 and info.get("column") == 1:
                    widget.configure(text_color=hex_color)
                    break

    def _on_slider(self, idx: int, val: float):
        pct = round(val)
        self.categories[idx]["percent"] = pct
        self.percent_labels[idx].configure(text=f"{pct}%")
        self.dollar_labels[idx].configure(text=f"${self._calc_dollar(pct):,.0f}")
        self._update_remaining()

    def _calc_dollar(self, pct: int) -> float:
        return self.total.get() * pct / 100

    # ── Footer ───────────────────────────────────────────────────────────
    def _build_footer(self):
        frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)
        frame.pack(fill="x", padx=24, pady=(12, 24))

        self.remaining_lbl = ctk.CTkLabel(
            frame, text="Remaining: $2,000", font=("Segoe UI", 16, "bold"),
            text_color=NEON_GREEN,
        )
        self.remaining_lbl.pack(side="left", padx=20, pady=16)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=20, pady=16)

        ctk.CTkButton(
            btn_frame, text="  Save  ", width=100, height=40,
            font=("Segoe UI", 14, "bold"), fg_color=BG_ENTRY,
            hover_color="#1a3a6a", corner_radius=10,
            command=self._save,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="  Load  ", width=100, height=40,
            font=("Segoe UI", 14, "bold"), fg_color=BG_ENTRY,
            hover_color="#1a3a6a", corner_radius=10,
            command=self._load,
        ).pack(side="left", padx=6)

        self._update_remaining()

    def _update_remaining(self):
        spent = sum(self._calc_dollar(c["percent"]) for c in self.categories)
        remaining = self.total.get() - spent
        color = NEON_GREEN if remaining >= 0 else NEON_RED
        prefix = "Remaining" if remaining >= 0 else "Over by"
        self.remaining_lbl.configure(
            text=f"{prefix}: ${abs(remaining):,.0f}", text_color=color
        )

    # ── Persistence ──────────────────────────────────────────────────────
    def _save(self):
        data = {
            "total": self.total.get(),
            "categories": [
                {"name": c["name"], "percent": c["percent"], "color": c["color"]}
                for c in self.categories
            ],
        }
        SAVE_PATH.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not SAVE_PATH.exists():
            return
        try:
            data = json.loads(SAVE_PATH.read_text())
            self.total.set(data["total"])
            for i, cat_data in enumerate(data["categories"]):
                if i >= len(self.categories):
                    break
                self.categories[i]["percent"] = cat_data["percent"]
                self.categories[i]["color"] = cat_data["color"]
                self.sliders[i].set(cat_data["percent"])
                self.percent_labels[i].configure(text=f"{cat_data['percent']}%")
                self.dollar_labels[i].configure(
                    text=f"${self._calc_dollar(cat_data['percent']):,.0f}",
                    text_color=cat_data["color"],
                )
                self.swatches[i].configure(
                    fg_color=cat_data["color"], hover_color=cat_data["color"]
                )
                self.sliders[i].configure(
                    progress_color=cat_data["color"],
                    button_color=cat_data["color"],
                    button_hover_color=cat_data["color"],
                )
                for widget in self.cat_frame.winfo_children():
                    info = widget.grid_info()
                    if info.get("row") == i + 1 and info.get("column") == 1:
                        widget.configure(text_color=cat_data["color"])
                        break
            self._update_remaining()
        except (json.JSONDecodeError, KeyError):
            pass


if __name__ == "__main__":
    app = BudgetApp()
    app.mainloop()
