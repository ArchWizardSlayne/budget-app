#!/usr/bin/env python3
"""Neon Budget Tracker — Modern GUI built with CustomTkinter."""

import json                # save/load budget data to/from the JSON save file
import tkinter as tk       # provides the tk.BooleanVar / tk.StringVar variables
from tkinter import colorchooser     # native OS color-picker dialog for category swatches
from tkinter import messagebox       # error dialogs for failed save/load
from pathlib import Path   # cross-platform path helper for locating the save file

import customtkinter as ctk  # the GUI toolkit this app is built on

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")          # force dark mode across the whole app
ctk.set_default_color_theme("dark-blue") # stock accent palette for built-in widgets

BG = "#1a1a2e"         # main window background — deep night purple
BG_FRAME = "#16213e"   # panel (frame) background — slightly lighter navy
BG_ENTRY = "#0f3460"   # input/entry background — vivid blue
NEON_GREEN = "#00ff41" # positive / leftover-money accent color
NEON_RED = "#ff0040"   # negative / over-budget accent color
FG = "#e0e0e0"         # primary text color — soft white
FG_DIM = "#8892a0"     # dimmed (captions, headers) text color — muted grey-blue

DEFAULT_TOTAL = 2000   # starting budget in dollars, used until the user sets one
DEFAULT_CATEGORIES = [ # categories shown when no budget.json exists yet
    {"name": "Rent", "percent": 0, "color": "#ff00ff"},       # purple accent
    {"name": "Food", "percent": 0, "color": "#00ffff"},       # cyan accent
    {"name": "Transport", "percent": 0, "color": "#ffff00"},  # yellow accent
    {"name": "Fun", "percent": 0, "color": "#ff6600"},        # orange accent
    {"name": "Savings", "percent": 0, "color": "#00ff41"},    # green accent
]
NEW_CATEGORY_COLORS = [  # palette cycled through for categories added at runtime
    "#ff66cc", "#66ccff", # pink and blue accents
    "#ffcc33", "#99ff66", # gold and lime accents
    "#cc66aa", "#66ffcc", # purple-pink and mint accents
]

# The save file lives next to this script, inside the app folder.
SAVE_PATH = Path(__file__).parent / "budget.json"


# ── Profile name dialog ─────────────────────────────────────────────────────
class ProfileNameDialog(ctk.CTkToplevel):
    """Small neon-styled popup that asks the user for a profile name."""

    def __init__(self, master, title: str, initial: str = ""):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=BG_FRAME)
        self.resizable(False, False)
        self._result: str | None = None
        self._closed = False

        self.after(200, self._center_over, master)  # center once the popup has its final size

        ctk.CTkLabel(
            self, text=title, font=("Segoe UI", 15, "bold"), text_color=FG_DIM
        ).pack(padx=24, pady=(18, 6))

        self.entry = ctk.CTkEntry(
            self, width=240, height=40, font=("Segoe UI", 15, "bold"),
            fg_color=BG_ENTRY, text_color=FG,
            border_color=NEON_GREEN, border_width=2, corner_radius=10,
        )
        self.entry.insert(0, initial)
        self.entry.pack(padx=24, pady=6)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(padx=24, pady=(6, 18))
        ctk.CTkButton(
            buttons, text="Cancel", width=92, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=BG_ENTRY, hover_color="#1a3a6a", corner_radius=10,
            command=self._cancel,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            buttons, text="OK", width=92, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=NEON_GREEN, hover_color="#00d43a", corner_radius=10,
            text_color="#001a10",
            command=self._confirm,
        ).pack(side="left", padx=6)

        self.entry.bind("<Return>", lambda _e: self._confirm())
        self.entry.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.entry.focus_set()
        self.entry.select_range(0, "end")  # highlight the old text so typing replaces it
        self.grab_set()                     # block the main window until the popup is dismissed
        self.wait_window()                  # pause here until the popup is destroyed

    def _center_over(self, master):
        self.update_idletasks()  # make sure the popup has its final dimensions
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _confirm(self):
        self._result = self.entry.get()
        self._close()

    def _cancel(self):
        self._result = None
        self._close()

    def _close(self):
        if self._closed:
            return
        self._closed = True
        self.grab_release()
        self.destroy()

    @property
    def result(self) -> str | None:
        return self._result


# ── App ──────────────────────────────────────────────────────────────────────
class BudgetApp(ctk.CTk):
    def __init__(self):
        super().__init__()              # let CustomTkinter set up the underlying window
        self.title("Budget Tracker")
        self.geometry("920x720")        # default window size on launch
        self.configure(fg_color=BG)     # tint the window background to match the theme
        self.minsize(780, 680)          # smallest size the user can resize down to

        self.resizable(True, True)      # allow resizing in both directions
        self.total = tk.StringVar(value=str(DEFAULT_TOTAL))  # shared variable bound to the total entry
        self._last_valid_total = DEFAULT_TOTAL  # fallback amount kept when the entry holds garbage
        self.locked = tk.BooleanVar(value=True)      # whether the total entry is read-only
        self.categories: list[dict] = []             # working data per category: name/percent/color
        self.sliders: list[ctk.CTkSlider] = []       # references to each percentage slider widget
        self.percent_labels: list[ctk.CTkLabel] = [] # references to each "%" label widget
        self.dollar_labels: list[ctk.CTkLabel] = []  # references to each "$" label widget
        self.swatches: list[ctk.CTkButton] = []      # references to each color swatch button
        self.delete_buttons: list[ctk.CTkButton] = []  # references to each delete button
        self.name_widgets: list[ctk.CTkLabel | ctk.CTkEntry | None] = [] # name is a label, an in-edit entry, or nothing

        self.profiles: dict[str, dict] = {}          # saved budgets: profile name -> {"total", "categories"}
        self.active_profile = "Default"              # which saved budget is currently on screen

        self._build_profile_bar()  # profile switcher bar at the very top
        self._build_top()          # header area: total amount + lock button
        self._build_categories()   # the category rows (swatch, name, slider, labels)
        self._build_footer()       # footer area: remaining readout + Save/Reload buttons
        self._load_storage()               # restore every saved profile (migrating a legacy file if needed)
        self._apply_active_profile()       # draw the last-active profile into the widgets
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # autosave the active profile on exit

    # ── Profile bar ─────────────────────────────────────────────────────
    def _build_profile_bar(self):
        frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)  # rounded panel for the switcher
        frame.pack(fill="x", padx=24, pady=(24, 0))  # full-width at the very top of the window

        ctk.CTkLabel(
            frame, text="PROFILE", font=("Segoe UI", 18, "bold"),
            text_color=FG_DIM
        ).pack(side="left", padx=(20, 10), pady=14)  # caption left of the dropdown

        self.profile_menu = ctk.CTkOptionMenu(
            frame, width=210, height=42,
            font=("Segoe UI", 15, "bold"),
            fg_color=BG_ENTRY,
            button_color=BG_ENTRY,
            button_hover_color="#1a3a6a",
            dropdown_fg_color=BG_FRAME,
            dropdown_hover_color="#1a3a6a",
            dropdown_text_color=FG,
            text_color=FG,
            corner_radius=10,
            command=self._on_profile_changed,  # switching autosaves the current profile, then loads the chosen one
        )
        self.profile_menu.pack(side="left", padx=(4, 0), pady=14)

        controls = ctk.CTkFrame(frame, fg_color="transparent")  # add/rename/delete buttons on the right
        controls.pack(side="right", padx=16, pady=14)

        ctk.CTkButton(
            controls, text="+ Add", width=72, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            corner_radius=10,
            command=self._add_profile,  # create a brand-new empty profile and jump into it
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls, text="Rename", width=84, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            corner_radius=10,
            command=self._rename_profile,  # re-label the active profile
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls, text="Delete", width=84, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#a01a2e",
            corner_radius=10,
            command=self._delete_profile,  # remove the active profile (never the last one)
        ).pack(side="left", padx=4)

    # ── Profiles ──────────────────────────────────────────────────────
    def _profile_names(self) -> list[str]:
        return list(self.profiles.keys())

    def _refresh_profile_menu(self):
        # Rebuild the dropdown's entries and park it on the active profile.
        self.profile_menu.configure(values=self._profile_names())
        self.profile_menu.set(self.active_profile)

    def _on_profile_changed(self, name: str):
        if name == self.active_profile or name not in self.profiles:
            return  # no-op: same profile, or a name that no longer exists
        self._save_current_profile()  # autosave the budget we're leaving behind...
        self.active_profile = name    # ...then switch to the newly chosen one
        self._apply_active_profile()

    def _save_current_profile(self):
        # Pull the on-screen budget into this profile's slot in the profiles dict.
        self.profiles[self.active_profile] = {
            "total": self._get_total(),
            "categories": [
                {"name": c["name"], "percent": c["percent"], "color": c["color"]}
                for c in self.categories
            ],
        }

    def _add_profile(self):
        name = (ProfileNameDialog(self, "Name the new budget profile", "").result or "").strip()
        if not name:
            return  # dialog cancelled or blank
        if name in self.profiles:
            messagebox.showwarning("Duplicate name", f"A profile named “{name}” already exists.")
            return
        self._save_current_profile()  # autosave the one we're leaving before creating the new one
        self.profiles[name] = {
            "total": DEFAULT_TOTAL,
            "categories": [dict(c) for c in DEFAULT_CATEGORIES],
        }
        self.active_profile = name    # jump straight into the brand-new profile
        self._refresh_profile_menu()
        self._apply_active_profile()

    def _rename_profile(self):
        old = self.active_profile
        name = (ProfileNameDialog(self, "Rename budget profile", old).result or "").strip()
        if not name or name == old:
            return  # cancelled, blank, or unchanged
        if name in self.profiles:
            messagebox.showwarning("Duplicate name", f"A profile named “{name}” already exists.")
            return
        self.profiles[name] = self.profiles.pop(old)  # move the data to the new key in place
        self.active_profile = name
        self._refresh_profile_menu()

    def _delete_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("Cannot delete", "You must keep at least one budget profile.")
            return
        ok = messagebox.askyesno(
            "Delete profile",
            f"Delete the “{self.active_profile}” budget profile? This cannot be undone.",
        )
        if not ok:
            return
        del self.profiles[self.active_profile]
        self.active_profile = self._profile_names()[0]  # land on whichever profile is left
        self._refresh_profile_menu()
        self._apply_active_profile()

    # ── Top: Total Budget ────────────────────────────────────────────────
    def _build_top(self):
        frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)  # rounded panel for the header
        # Stretch full-width at the top of the window, with breathing room around it.
        frame.pack(fill="x", padx=24, pady=(24, 14))

        ctk.CTkLabel(
            frame, text="TOTAL BUDGET", font=("Segoe UI", 18, "bold"),
            text_color=FG_DIM
        ).pack(side="left", padx=(20, 10), pady=22)  # caption sits left of the amount box

        # Larger, glowing entry that displays/edits the total amount.
        self.total_entry = ctk.CTkEntry(
            frame, textvariable=self.total,
            width=170, height=52,
            font=("Consolas", 34, "bold"),
            fg_color=BG_ENTRY,
            text_color=NEON_GREEN,
            border_color=NEON_GREEN,
            border_width=2,
            corner_radius=12,
            justify="center",
            state="disabled",  # read-only until the user clicks "LOCKED"
        )
        self.total_entry.pack(side="left", padx=4, pady=22)

        ctk.CTkLabel(
            frame, text="$", font=("Consolas", 34, "bold"),
            text_color=NEON_GREEN
        ).pack(side="left", padx=(0, 10), pady=22)  # currency prefix for the amount

        self.lock_btn = ctk.CTkButton(
            frame, text="LOCKED", width=110, height=44, corner_radius=12,
            font=("Segoe UI", 15, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            command=self._toggle_lock,  # clicking toggles editability of the total
        )
        self.lock_btn.pack(side="left", padx=(14, 20), pady=22)

    def _toggle_lock(self):
        # Flip the lock, then sync the entry and button widgets.
        self.locked.set(not self.locked.get())
        self._apply_lock_state()

    def _apply_lock_state(self):
        # Sync the total entry and lock button with the current lock flag.
        if self.locked.get():
            self.total.set(str(self._get_total()))  # revert any garbage back to the last valid amount
            self.total_entry.configure(state="disabled")  # lock: grey the entry out
            self.lock_btn.configure(text="LOCKED")
        else:
            self.total_entry.configure(state="normal")    # unlock: let the user type
            self.lock_btn.configure(text="UNLOCKED")
            self.total_entry.focus_set()                  # drop the cursor into the entry

    # ── Categories ───────────────────────────────────────────────────────
    def _build_categories(self):
        panel = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)
        # fill/expand makes this panel grow to use all leftover vertical space.
        panel.pack(fill="both", expand=True, padx=24, pady=12)

        # Fixed header: the panel title and the add button stay put while the
        # category rows below can scroll within the scrollable frame.
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            header, text="CATEGORIES", font=("Segoe UI", 16, "bold"),
            text_color=FG_DIM
        ).pack(side="left", padx=12, pady=6)

        ctk.CTkButton(
            header, text="+ Add Category", width=130, height=34,
            font=("Segoe UI", 14, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            corner_radius=10,
            command=self._add_category,  # clicking appends a brand-new category row
        ).pack(side="right", padx=12, pady=6)

        self.cat_frame = ctk.CTkScrollableFrame(panel, fg_color=BG_FRAME, corner_radius=0)
        self.cat_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        # Grid columns: 0=swatch, 1=name, 2=slider, 3=%, 4=$, 5=delete button. 
        self.cat_frame.columnconfigure(0, weight=0)  # fixed width
        self.cat_frame.columnconfigure(1, weight=0)  # fixed width
        self.cat_frame.columnconfigure(2, weight=1)  # slider column absorbs extra width
        self.cat_frame.columnconfigure(3, weight=0)  # fixed width
        self.cat_frame.columnconfigure(4, weight=0)  # fixed width
        self.cat_frame.columnconfigure(5, weight=0)  # fixed width

        # Create one default category row per entry.
        self.categories = [dict(cat) for cat in DEFAULT_CATEGORIES]  # working copies, so edits never touch the defaults
        for i, cat in enumerate(self.categories):
            self._add_category_row(i, cat)

    def _add_category_row(self, idx: int, cat: dict):
        # Convenient local copies of this category's saved settings.
        color = cat["color"]
        pct = cat["percent"]
        name = cat["name"]

        # color swatch (clickable)
        swatch = ctk.CTkButton(
            self.cat_frame, text="", width=34, height=34,
            fg_color=color, hover_color=color, corner_radius=10,
            border_width=2, border_color="#ffffff",
            command=lambda i=idx: self._pick_color(i),  # open color picker on click
        )
        swatch.grid(row=idx, column=0, padx=(24, 12), pady=14, sticky="w")
        self.swatches.append(swatch)

        # category name
        name_lbl = ctk.CTkLabel(
            self.cat_frame, text=name, font=("Segoe UI", 22, "bold"),
            text_color=color, width=140, anchor="w", cursor="hand2",
        )
        name_lbl.grid(row=idx, column=1, padx=(0, 12), pady=14, sticky="w")
        name_lbl.bind("<Button-1>", lambda _e, i=idx: self._start_rename(i))  # click name to rename
        self.name_widgets.append(name_lbl)

        # slider
        slider = ctk.CTkSlider(
            self.cat_frame, from_=0, to=100, number_of_steps=100,  # whole-percent steps
            height=26, corner_radius=13,
            fg_color="#2a2a4a", progress_color=color,
            button_color=color, button_hover_color=self._lighten(color),
            command=lambda val, i=idx: self._on_slider(i, val),  # live-update as you drag
        )
        slider.set(pct)
        slider.grid(row=idx, column=2, padx=12, pady=14, sticky="ew")
        self.sliders.append(slider)

        # percent label
        pct_lbl = ctk.CTkLabel(
            self.cat_frame, text=f"{pct}%", font=("Consolas", 20, "bold"),
            text_color=FG, width=60, anchor="e",
        )
        pct_lbl.grid(row=idx, column=3, padx=(4, 10), pady=14)
        self.percent_labels.append(pct_lbl)

        # dollar label
        dollar = self._calc_dollar(pct)   # convert percentage into a real dollar amount
        dol_lbl = ctk.CTkLabel(
            self.cat_frame, text=f"${dollar:,.0f}",
            font=("Consolas", 20, "bold"), text_color=color,
            width=120, anchor="e",
        )
        dol_lbl.grid(row=idx, column=4, padx=(0, 24), pady=14, sticky="e")
        self.dollar_labels.append(dol_lbl)

        # delete button (removes this row entirely)
        delete_btn = ctk.CTkButton(
            self.cat_frame, text="✕", width=34, height=34,
            font=("Segoe UI", 18, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#a01a2e",
            corner_radius=10,
            command=lambda i=idx: self._delete_category(i),  # strip this category on click
        )
        delete_btn.grid(row=idx, column=5, padx=(0, 24), pady=14, sticky="e")
        self.delete_buttons.append(delete_btn)

    def _lighten(self, hex_color: str, amount: float = 0.35) -> str:
        """Lighten a hex color toward white for hover states."""
        # Mix each RGB channel toward 255 by `amount` (a fraction between 0.0 and 1.0).
        hex_color = hex_color.lstrip("#")                     # drop the leading "#" for parsing
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # split the 6-digit hex into RGB
        r = round(r + (255 - r) * amount)                     # push red channel toward white
        g = round(g + (255 - g) * amount)                     # push green channel toward white
        b = round(b + (255 - b) * amount)                     # push blue channel toward white
        return f"#{r:02x}{g:02x}{b:02x}"                      # re-format back into a hex color string

    def _is_hex(self, value: str) -> bool:
        # True when the value is a #rrggbb hex color string (e.g. "#00ff41").
        try:
            digits = value.lstrip("#")
            return len(digits) == 6 and int(digits, 16) >= 0
        except (ValueError, TypeError, AttributeError):
            return False

    def _pick_color(self, idx: int):
        current = self.categories[idx]["color"]  # open the picker pre-selected on the current color
        result = colorchooser.askcolor(
            initialcolor=current, title=f"Pick color for {self.categories[idx]['name']}"
        )
        if result and result[1]:  # only proceed if the user chose a color (didn't cancel)
            hex_color = result[1]
            hover = self._lighten(hex_color)  # derive a matching lighter shade for hover states
            self.categories[idx]["color"] = hex_color
            self.swatches[idx].configure(fg_color=hex_color, hover_color=hex_color)
            self.dollar_labels[idx].configure(text_color=hex_color)
            # update slider colors
            self.sliders[idx].configure(
                progress_color=hex_color,
                button_color=hex_color,
                button_hover_color=hover,
            )
            # update category name color
            if isinstance(self.name_widgets[idx], ctk.CTkEntry):
                self.name_widgets[idx].configure(text_color=hex_color, border_color=hex_color)
            elif self.name_widgets[idx] is not None:
                self.name_widgets[idx].configure(text_color=hex_color)

    def _start_rename(self, idx: int):
        col1_row = idx  # grid rows match the category index (row 0 is the first category)
        if isinstance(self.name_widgets[idx], ctk.CTkEntry):
            return  # already editing this name — ignore duplicate clicks
        color = self.categories[idx]["color"]
        original = self.categories[idx]["name"]

        # Swap the clickable label for a text entry pre-filled with the current name.
        self.name_widgets[idx].destroy()
        entry = ctk.CTkEntry(
            self.cat_frame,
            font=("Segoe UI", 18, "bold"),
            text_color=color,
            width=140,
            fg_color=BG_ENTRY,
            border_color=color,
            border_width=2,
            corner_radius=8,
            justify="left",
        )
        entry.insert(0, original)
        entry.grid(row=col1_row, column=1, padx=(0, 12), pady=14, sticky="w")
        self.name_widgets[idx] = entry

        # Enter/FocusOut commit the rename; Escape restores the original instead.
        entry.bind("<Return>", lambda _e: self._confirm_rename(idx, original))
        entry.bind("<Escape>", lambda _e: self._cancel_rename(idx, original))
        entry.bind("<FocusOut>", lambda _e: self._confirm_rename(idx, original))
        entry.focus_set()
        entry.select_range(0, "end")  # highlight the old text so typing replaces it

    def _confirm_rename(self, idx: int, original: str):
        entry = self.name_widgets[idx]
        if not isinstance(entry, ctk.CTkEntry):
            return  # widget is already back to a label — nothing to confirm
        new_name = entry.get().strip()
        if not new_name:
            new_name = original  # fall back to the old name if the box was cleared
        self.categories[idx]["name"] = new_name
        self._replace_name_with_label(idx, new_name)  # put the label back with the new text

    def _cancel_rename(self, idx: int, original: str):
        # Throw away whatever was typed and restore the original name as a label.
        if not isinstance(self.name_widgets[idx], ctk.CTkEntry):
            return
        self._replace_name_with_label(idx, original)

    def _replace_name_with_label(self, idx: int, name: str):
        col1_row = idx
        color = self.categories[idx]["color"]
        self.name_widgets[idx].destroy()
        # Rebuild the clickable label that re-enters rename mode when clicked.
        name_lbl = ctk.CTkLabel(
            self.cat_frame, text=name, font=("Segoe UI", 22, "bold"),
            text_color=color, width=140, anchor="w", cursor="hand2",
        )
        name_lbl.grid(row=col1_row, column=1, padx=(0, 12), pady=14, sticky="w")
        name_lbl.bind("<Button-1>", lambda _e, i=idx: self._start_rename(i))
        self.name_widgets[idx] = name_lbl

    def _on_slider(self, idx: int, val: float):
        pct = round(val)  # slider reports a float; snap it to a whole percentage
        self.categories[idx]["percent"] = pct
        self.percent_labels[idx].configure(text=f"{pct}%")
        self.dollar_labels[idx].configure(text=f"${self._calc_dollar(pct):,.0f}")
        self.sliders[idx].set(pct)  # snap the thumb to the rounded value so it matches the labels
        self._update_remaining()  # footer must re-total as soon as a split changes

    def _get_total(self) -> int:
        # Parse the total entry's text; fall back to the last valid amount if it holds garbage.
        raw = self.total.get()
        try:
            parsed = max(0, int(float(raw.replace(",", ""))))
        except (ValueError, TypeError):
            parsed = self._last_valid_total
        self._last_valid_total = parsed
        return parsed

    def _calc_dollar(self, pct: int) -> float:
        # Convert a percentage of the overall total into the corresponding dollar figure.
        return self._get_total() * pct / 100

    def _add_category(self):
        # Append a fresh empty category and build its row immediately;
        # the existing click-to-rename flow lets the user name it right away.
        color = NEW_CATEGORY_COLORS[len(self.categories) % len(NEW_CATEGORY_COLORS)]  # cycle so neighbors keep distinct hues
        new_cat = {"name": "New Category", "percent": 0, "color": color}
        self.categories.append(new_cat)  # register it in the working list first...
        self._add_category_row(len(self.categories) - 1, new_cat)  # ...then draw its row at the index it now holds
        self._update_remaining()  # keep the footer readout fresh (0% adds nothing, but stay consistent)

    def _delete_category(self, idx: int):
        # Never drop the last category so the panel always keeps at least one row.
        if len(self.categories) == 1:
            return
        self.categories.pop(idx)  # remove it from the working list...
        self._rebuild_rows()      # ...then re-lay out every row so grid rows and widget indices stay aligned

    def _rebuild_rows(self):
        # A mid-list deletion shifts every later row, so rebuild all of them from
        # scratch: destroy the old row widgets, then recreate one per category.
        for widget in self.cat_frame.grid_slaves():
            widget.destroy()
        self.swatches.clear()
        self.percent_labels.clear()
        self.dollar_labels.clear()
        self.delete_buttons.clear()
        self.sliders.clear()
        self.name_widgets.clear()
        for i, cat in enumerate(self.categories):
            self._add_category_row(i, cat)
        self._update_remaining()  # footer re-totals now that the row count has changed

    # ── Footer ───────────────────────────────────────────────────────────
    def _build_footer(self):
        frame = ctk.CTkFrame(self, fg_color=BG_FRAME, corner_radius=16)  # rounded bottom panel
        frame.pack(fill="x", padx=24, pady=(14, 24))

        self.remaining_lbl = ctk.CTkLabel(
            frame, text="Remaining: $2,000", font=("Segoe UI", 20, "bold"),
            text_color=NEON_GREEN,
        )
        self.remaining_lbl.pack(side="left", padx=24, pady=18)  # leftover/overage readout on the left

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")  # groups the two buttons on the right
        btn_frame.pack(side="right", padx=24, pady=18)

        ctk.CTkButton(
            btn_frame, text="  Save  ", width=110, height=46,
            font=("Segoe UI", 16, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            corner_radius=12,
            command=self._save,  # persist every profile (and the active one) to budget.json
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="  Reload  ", width=110, height=46,
            font=("Segoe UI", 16, "bold"),
            fg_color=BG_ENTRY,
            hover_color="#1a3a6a",
            corner_radius=12,
            command=self._reload_active,  # discard unsaved edits and restore the profile from disk
        ).pack(side="left", padx=6)

        self._update_remaining()  # refresh the footer readout once at startup

    def _update_remaining(self):
        spent = sum(self._calc_dollar(c["percent"]) for c in self.categories)  # dollars already allocated
        remaining = self._get_total() - spent
        color = NEON_GREEN if remaining >= 0 else NEON_RED  # green for leftover, red for overruns
        prefix = "Remaining" if remaining >= 0 else "Over by"
        self.remaining_lbl.configure(
            text=f"{prefix}: ${abs(remaining):,.0f}", text_color=color
        )

    # ── Persistence ──────────────────────────────────────────────────────
    def _default_profile(self) -> dict:
        return {
            "total": DEFAULT_TOTAL,
            "categories": [dict(c) for c in DEFAULT_CATEGORIES],
        }

    def _validate_budget_data(self, data) -> dict:
        # Check one profile's worth of saved data and return a sanitized copy;
        # raises on malformed input so the caller can abort without mutating UI state.
        total = max(0, int(float(str(data.get("total")).replace(",", ""))))
        categories = []
        for c in data["categories"]:
            categories.append({
                "name": str(c["name"]),
                "percent": max(0, min(100, int(float(c["percent"])))),
                "color": c["color"] if self._is_hex(c["color"]) else "#8888aa",
            })
        if not categories:  # never let a profile end up with zero rows
            categories = [dict(c) for c in DEFAULT_CATEGORIES]
        return {"total": total, "categories": categories}

    def _save(self):
        # Persist the whole profile store (active marker + every profile).
        self._save_current_profile()  # snapshot the on-screen budget into its profile slot first
        try:
            SAVE_PATH.write_text(
                json.dumps(
                    {"active": self.active_profile, "profiles": self.profiles},
                    indent=2, ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except (OSError, UnicodeEncodeError):
            messagebox.showerror(
                "Save failed",
                "Could not save your budget. Check that the file is writable and not open elsewhere.",
            )

    def _load_storage(self):
        # Load every saved profile. A missing file starts a single "Default"
        # profile; a legacy single-budget file silently migrates into "Default".
        if not SAVE_PATH.exists():
            self.profiles = {"Default": self._default_profile()}
            self.active_profile = "Default"
            self._refresh_profile_menu()
            return
        try:
            data = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
            if "profiles" not in data:
                # Legacy format: one budget with no profile wrapper.
                profiles = {"Default": self._validate_budget_data(data)}
                active = "Default"
            else:
                profiles = {
                    str(name): self._validate_budget_data(prof)
                    for name, prof in data["profiles"].items()
                }
                active = str(data.get("active") or "")
                if active not in profiles:  # saved marker points somewhere unknown
                    active = next(iter(profiles), "Default")
        except (KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError):
            messagebox.showerror(
                "Load failed",
                "Could not load your budget from budget.json. "
                "The file may be corrupt or was edited by hand.",
            )
            self.profiles = {"Default": self._default_profile()}
            self.active_profile = "Default"
            self._refresh_profile_menu()
            return  # nothing was mutated — the current budget stays intact

        if not profiles:  # file was valid but held no profiles at all
            profiles = {"Default": self._default_profile()}
        self.profiles = profiles
        self.active_profile = active
        self._refresh_profile_menu()

    def _apply_active_profile(self):
        # Commit one profile's saved data into the on-screen widgets.
        profile = self.profiles.get(self.active_profile)
        if profile is None:
            return
        self.total.set(str(profile["total"]))
        self._last_valid_total = profile["total"]
        self.categories = [dict(c) for c in profile["categories"]]
        self._rebuild_rows()
        self.locked.set(True)      # a load restores a saved budget, so the entry starts read-only
        self._apply_lock_state()
        self._refresh_profile_menu()  # keep the dropdown label in sync with the active profile

    def _reload_active(self):
        # Discard unsaved edits and restore the active profile from disk.
        self._load_storage()
        self._apply_active_profile()

    def _on_close(self):
        self._save_current_profile()  # autosave the active profile before the window closes
        self.destroy()


if __name__ == "__main__":
    app = BudgetApp()  # build the window
    app.mainloop()     # start the GUI event loop (runs until the window is closed)
