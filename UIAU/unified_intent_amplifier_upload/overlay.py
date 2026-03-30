"""
overlay.py — Always-on-top control panel for Unified Intent Amplifier.

Layout:
  [Title bar + close]
  [4 feature toggle buttons]
  [Language selector: EN | ZU | ST | AF]
  [AI suggestion / coaching tip bar]
  [Cognitive toggle + Quit]
"""

import tkinter as tk
import threading
import logging
from config import OVERLAY_BG, OVERLAY_FG, OVERLAY_ACCENT

logger = logging.getLogger(__name__)

PANEL_W = 480
PANEL_H = 240

LANG_CODES = ["English", "isiZulu", "Sesotho", "Afrikaans"]
LANG_LABELS = ["EN 🇿🇦", "ZU", "ST", "AF"]


class OverlayWindow:
    """Full control panel: feature toggles, language switcher, AI tip bar."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Unified Intent Amplifier")
        self.root.geometry(f"{PANEL_W}x{PANEL_H}+30+30")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.overrideredirect(True)
        self.root.configure(bg=OVERLAY_BG)
        self.root.resizable(False, False)

        # Callbacks wired by main.py
        self.on_toggle = {}
        self.on_language = None
        self.on_cognitive = None
        self.on_read_screen = None   # instant screen read
        self.on_ask_voice = None        # NEW: text question → GPT-4o answer
        self.on_ask_voice_record = None  # NEW: record mic → transcribed text
        self.on_ideas = None            # NEW: idea generation
        self._listening = False

        self._state = {
            "gaze":    False,  # OFF by default
            "tremor":  False,  # OFF by default
            "typing":  True,
            "audio":   False,
        }
        self._cognitive_on = False
        self._current_lang = "English"

        self._dx = self._dy = 0
        self.root.bind("<ButtonPress-1>", self._drag_start)
        self.root.bind("<B1-Motion>",     self._drag_move)

        self._build_ui()

    def _build_ui(self):

        # ── Title bar ─────────────────────────────────────────────────────
        title = tk.Frame(self.root, bg="#0a0a1a", height=30)
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        title.bind("<ButtonPress-1>", self._drag_start)
        title.bind("<B1-Motion>",     self._drag_move)

        tk.Label(title, text="  ✦ Unified Intent Amplifier",
                 bg="#0a0a1a", fg=OVERLAY_ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, pady=5)

        tk.Button(title, text=" ✕ ", bg="#0a0a1a", fg="#666",
                  relief=tk.FLAT, font=("Segoe UI", 11, "bold"),
                  activebackground="#cc2222", activeforeground="white",
                  command=self.root.destroy, cursor="hand2").pack(side=tk.RIGHT, padx=4)

        # ── Feature buttons ───────────────────────────────────────────────
        feat_frame = tk.Frame(self.root, bg=OVERLAY_BG)
        feat_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self._buttons = {}
        features = [
            ("gaze",   "👁 Gaze"),
            ("tremor", "🖱 Tremor"),
            ("typing", "⌨ Typing"),
            ("audio",  "🔊 Audio"),
        ]
        for col, (key, label) in enumerate(features):
            active = self._state[key]
            btn = tk.Button(
                feat_frame, text=label,
                bg=OVERLAY_ACCENT if active else "#1a1a3a",
                fg="#000" if active else OVERLAY_FG,
                font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT, width=10, height=2,
                cursor="hand2",
                command=lambda k=key: self._toggle(k),
            )
            btn.grid(row=0, column=col, padx=3)
            self._buttons[key] = btn

        # ── Language selector ─────────────────────────────────────────────
        lang_frame = tk.Frame(self.root, bg=OVERLAY_BG)
        lang_frame.pack(fill=tk.X, padx=8, pady=(2, 4))

        tk.Label(lang_frame, text="Lang:", bg=OVERLAY_BG, fg="#778",
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)

        self._lang_buttons = {}
        for lang, label in zip(LANG_CODES, LANG_LABELS):
            is_active = (lang == self._current_lang)
            btn = tk.Button(
                lang_frame, text=label,
                bg=OVERLAY_ACCENT if is_active else "#1a1a3a",
                fg="#000" if is_active else "#aaa",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, width=5,
                cursor="hand2",
                command=lambda l=lang: self._set_language(l),
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._lang_buttons[lang] = btn

        # ── AI tip / suggestion bar ───────────────────────────────────────
        tip_frame = tk.Frame(self.root, bg="#0a0a1a")
        tip_frame.pack(fill=tk.X)

        self._lbl_tip = tk.Label(
            tip_frame,
            text="✦ Click a feature to activate  •  Drag title to move",
            bg="#0a0a1a", fg="#99aacc",
            font=("Segoe UI", 8),
            wraplength=PANEL_W - 20,
            justify=tk.LEFT, anchor="w",
        )
        self._lbl_tip.pack(fill=tk.X, padx=10, pady=5)

        # ── Bottom bar: cognitive toggle + quit ───────────────────────────
        bot_frame = tk.Frame(self.root, bg=OVERLAY_BG)
        bot_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        self._btn_cognitive = tk.Button(
            bot_frame,
            text="🧠 AI Assist: OFF",
            bg="#1a1a3a", fg="#888",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, cursor="hand2",
            command=self._toggle_cognitive,
        )
        self._btn_cognitive.pack(side=tk.LEFT)

        # ── Dedicated OFF button ─────────────────────────────────────────
        self._btn_ai_off = tk.Button(
            bot_frame,
            text="🔴 AI OFF",
            bg="#8B0000", fg="#fff",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, cursor="hand2",
            command=self._force_ai_off,
        )
        self._btn_ai_off.pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(
            bot_frame,
            text="📸 Read Screen Now",
            bg="#1a1a3a", fg="#aaa",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, cursor="hand2",
            command=self._read_screen_now,
        ).pack(side=tk.LEFT, padx=(6, 0))

        self._btn_ask = tk.Button(
            bot_frame,
            text="🎤 Ask",
            bg="#1a1a3a", fg="#aaa",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, cursor="hand2",
            command=self._ask_voice,
        )
        self._btn_ask.pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(
            bot_frame, text="💡 Ideas",
            bg="#1a1a3a", fg="#aaa",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, cursor="hand2",
            command=self._request_ideas,
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(
            bot_frame, text="Quit",
            bg="#1a1a3a", fg="#666",
            font=("Segoe UI", 8),
            relief=tk.FLAT, cursor="hand2",
            command=self.root.destroy,
        ).pack(side=tk.RIGHT)

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _initialize_features(self):
        """Call toggle callbacks for features that are ON by default."""
        for feature, enabled in self._state.items():
            if enabled:
                cb = self.on_toggle.get(feature)
                if cb:
                    cb(True)
                    logger.info("Feature initialized: %s = ON", feature)

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + (event.x - self._dx)
        y = self.root.winfo_y() + (event.y - self._dy)
        self.root.geometry(f"+{x}+{y}")

    # ── Feature toggle ────────────────────────────────────────────────────────

    def _toggle(self, feature):
        new_val = not self._state[feature]
        self._state[feature] = new_val
        self._buttons[feature].config(
            bg=OVERLAY_ACCENT if new_val else "#1a1a3a",
            fg="#000" if new_val else OVERLAY_FG,
        )
        cb = self.on_toggle.get(feature)
        if cb:
            cb(new_val)
        names = {"gaze": "Gaze", "tremor": "Tremor", "typing": "Typing", "audio": "Audio"}
        self.show_tip(f"{names[feature]}: {'ON ✓' if new_val else 'OFF'}")
        logger.info("Toggled %s → %s", feature, new_val)

    # ── Language ──────────────────────────────────────────────────────────────

    def _set_language(self, language):
        self._current_lang = language
        for lang, btn in self._lang_buttons.items():
            active = (lang == language)
            btn.config(
                bg=OVERLAY_ACCENT if active else "#1a1a3a",
                fg="#000" if active else "#aaa",
            )
        if self.on_language:
            self.on_language(language)
        self.show_tip(f"Language: {language}")
        logger.info("Language: %s", language)

    # ── Cognitive ─────────────────────────────────────────────────────────────

    def _toggle_cognitive(self):
        self._cognitive_on = not self._cognitive_on
        self._btn_cognitive.config(
            text=f"🧠 AI Assist: {'ON ✓' if self._cognitive_on else 'OFF'}",
            bg=OVERLAY_ACCENT if self._cognitive_on else "#1a1a3a",
            fg="#000" if self._cognitive_on else "#888",
        )
        if self.on_cognitive:
            self.on_cognitive(self._cognitive_on)

    def _force_ai_off(self):
        """Immediately force AI Assist to OFF state"""
        self._cognitive_on = False
        self._btn_cognitive.config(
            text="🧠 AI Assist: OFF",
            bg="#1a1a3a", fg="#888",
        )
        if self.on_cognitive:
            self.on_cognitive(False)
        self.show_tip("🔴 AI Assist Force Disabled")
        logger.info("AI Assist force disabled by user")

    def _ask_voice(self):
        """Open a popup where user can TYPE a question or press 🎤 to speak."""
        if self._listening:
            return
        self._show_ask_popup()

    def _show_ask_popup(self):
        """Small popup with a text entry + optional voice button."""
        popup = tk.Toplevel(self.root)
        popup.title("")
        popup.geometry("420x110+80+280")
        popup.attributes("-topmost", True)
        popup.configure(bg="#0a0a1a")
        popup.resizable(False, False)

        tk.Label(popup, text="Ask a question — type or speak:",
                 bg="#0a0a1a", fg="#99aacc",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(8, 2))

        entry_frame = tk.Frame(popup, bg="#0a0a1a")
        entry_frame.pack(fill=tk.X, padx=10)

        entry = tk.Entry(entry_frame, font=("Segoe UI", 10),
                         bg="#1a1a3a", fg="white", insertbackground="white",
                         relief=tk.FLAT, bd=4)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.focus_set()

        status = tk.Label(popup, text="", bg="#0a0a1a", fg="#cc8800",
                          font=("Segoe UI", 8))
        status.pack(anchor="w", padx=10)

        def _submit_text(event=None):
            q = entry.get().strip()
            if not q:
                return
            popup.destroy()
            self.show_tip(f"🎤 You asked: {q}")
            self._listening = True
            self._btn_ask.config(text="🧠 Thinking...", bg="#1a1a3a", fg="#cc8800")
            def _do():
                try:
                    if self.on_ask_voice:
                        self.on_ask_voice(q)
                finally:
                    self._listening = False
                    self.root.after(0, lambda: self._btn_ask.config(
                        text="🎤 Ask", bg="#1a1a3a", fg="#aaa"))
            threading.Thread(target=_do, daemon=True, name="AskVoice").start()

        def _submit_voice():
            status.config(text="🎤 Speak now — recording for 6 seconds...")
            popup.update()
            def _do():
                try:
                    result = self.on_ask_voice_record() if self.on_ask_voice_record else ""
                    if result and result.strip():
                        entry.delete(0, tk.END)
                        entry.insert(0, result.strip())
                        popup.after(0, lambda: status.config(
                            text=f'✓ Heard: "{result.strip()}" — edit if needed, then click Ask',
                            fg="#44cc44"))
                    else:
                        popup.after(0, lambda: status.config(
                            text="⚠ Mic picked up nothing — check mic is not muted, or just type your question",
                            fg="#cc8800"))
                except Exception as exc:
                    popup.after(0, lambda: status.config(
                        text=f"⚠ Mic error — please type your question instead",
                        fg="#cc4400"))
            threading.Thread(target=_do, daemon=True, name="VoiceRecord").start()

        btn_frame = tk.Frame(popup, bg="#0a0a1a")
        btn_frame.pack(fill=tk.X, padx=10, pady=(4, 0))

        tk.Button(btn_frame, text="✓ Ask", bg="#2255cc", fg="white",
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                  cursor="hand2", command=_submit_text).pack(side=tk.LEFT)

        tk.Button(btn_frame, text="🎤 Speak", bg="#1a1a3a", fg="#aaa",
                  font=("Segoe UI", 9), relief=tk.FLAT,
                  cursor="hand2", command=_submit_voice).pack(side=tk.LEFT, padx=(6,0))

        tk.Button(btn_frame, text="Cancel", bg="#1a1a3a", fg="#666",
                  font=("Segoe UI", 9), relief=tk.FLAT,
                  cursor="hand2", command=popup.destroy).pack(side=tk.RIGHT)

        entry.bind("<Return>", _submit_text)
        popup.bind("<Escape>", lambda e: popup.destroy())

    def _read_screen_now(self):
        """Trigger an immediate screen read in a background thread."""
        self.show_tip("📸 Reading screen...")
        if self.on_read_screen:
            threading.Thread(
                target=self.on_read_screen, daemon=True, name="ReadNow"
            ).start()
        logger.info("Cognitive: %s", self._cognitive_on)

    def _request_ideas(self):
        """Request 3 ideas from the agent team."""
        if self.on_ideas:
            threading.Thread(target=self.on_ideas, daemon=True,
                            name="Ideas").start()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_indicator(self, name, active):
        key = "typing" if name == "type" else name
        if key in self._state:
            self._state[key] = active
            btn = self._buttons.get(key)
            if btn:
                btn.config(
                    bg=OVERLAY_ACCENT if active else "#1a1a3a",
                    fg="#000" if active else OVERLAY_FG,
                )

    def show_tip(self, text):
        """Thread-safe status/tip update."""
        self.root.after(0, lambda: self._lbl_tip.config(text=f"✦ {text}"))

    def run(self):
        logger.info("Overlay running")
        self.root.mainloop()

    def run_in_thread(self):
        t = threading.Thread(target=self.run, daemon=True, name="Overlay")
        t.start()
        return t
