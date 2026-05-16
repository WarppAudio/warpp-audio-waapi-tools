import logging
import os
import socket
import tkinter.messagebox as mb
from pathlib import Path

import customtkinter as ctk
import numpy as np
from PIL import Image
from waapi import WaapiClient
import matplotlib

matplotlib.use('TkAgg')  # Must be called before importing pyplot, because pyplot locks in the backend on import.
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

WAAPI_HOST = "127.0.0.1"
WAAPI_PORT = 8080

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def setup_logging():
    log_level = os.environ.get("LOG_LEVEL")
    if not log_level:
        # Silence everything (waapi/matplotlib/PIL included) — a --windowed .exe has no console.
        logging.disable(logging.CRITICAL)
        return

    level = getattr(logging, log_level.upper(), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


ctk.set_appearance_mode("Dark")

ICON_DIR = Path(__file__).resolve().parent / "Icons"
ICON_CACHE: dict[tuple[str, tuple[int, int]], ctk.CTkImage] = {}


def get_icon(path: Path, size: tuple[int, int]) -> ctk.CTkImage:
    key = (str(path), size)
    if key not in ICON_CACHE:
        img = Image.open(path)
        ICON_CACHE[key] = ctk.CTkImage(light_image=img, dark_image=img, size=size)
    return ICON_CACHE[key]


def wwise_is_reachable(host=WAAPI_HOST, port=WAAPI_PORT, timeout=0.25):
    """One short TCP probe of Wwise's WAAPI port. WaapiClient() retries the
    connection internally when Wwise is closed, hanging startup for seconds; a
    single attempt capped at `timeout` keeps startup fast instead."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


attenuation_map = {
    "Volume": "VolumeDryUsage",
    "Auxiliary send volumes (Game-defined)": "VolumeWetGameUsage",
    "Auxiliary send volumes (User-defined)": "VolumeWetUserUsage",
    "Low-pass filter": "LowPassFilterUsage",
    "High-pass filter": "HighPassFilterUsage",
    "Spread": "SpreadUsage",
    "Focus": "FocusUsage",
    "Obstruction Volume": "ObstructionVolumeUsage",
    "Obstruction Low-pass filter": "ObstructionLPFUsage",
    "Obstruction High-pass filter": "ObstructionHPFUsage",
    "Occlusion Volume": "OcclusionVolumeUsage",
    "Occlusion Low-pass filter": "OcclusionLPFUsage",
    "Occlusion High-pass filter": "OcclusionHPFUsage",
    "Diffraction Volume": "DiffractionVolumeUsage",
    "Diffraction Low-pass filter": "DiffractionLPFUsage",
    "Diffraction High-pass filter": "DiffractionHPFUsage",
    "Transmission Volume": "TransmissionVolumeUsage",
    "Transmission Low-pass filter": "TransmissionLPFUsage",
    "Transmission High-pass filter": "TransmissionHPFUsage",
}

shape_display_map = {
    "Constant": "Constant",
    "Linear": "Linear",
    "Log3": "Logarithmic Base 3",
    "Log2": "Sine (Constant Power Fade In)",
    "Log1": "Logarithmic (Base 1.41)",
    "InvertedSCurve": "Inverted S-Curve",
    "SCurve": "S-Curve",
    "Exp1": "Exponential (Base 1.41)",
    "Exp2": "Sine (Constant Power Fade Out)",
    "Exp3": "Exponential Base 3"
}
display_to_shape = {disp: key for key, disp in shape_display_map.items()}

# dB axis mapping used by both the y-position helper and the graph y-ticks
Y_VALUES = [-200.0, -18.1, -12.0, -8.5, -6.0, -4.1, -2.5, -1.2, 0.0]
Y_POSITIONS = np.linspace(0.0, 1.0, num=9).tolist()


def linear_interpolation(x0, y0, x1, y1, num_points=50):
    x = np.linspace(x0, x1, num_points)
    y = np.linspace(y0, y1, num_points)
    return x, y


def logarithmic_interpolation(x0, y0, x1, y1, base, num_points=50):
    x = np.linspace(x0, x1, num_points)
    t = np.linspace(0, 1, num_points)
    log_scale = (np.log1p((base - 1) * t)) / np.log(base)
    y = y0 + (y1 - y0) * log_scale
    return x, y


def exponential_interpolation(x0, y0, x1, y1, exponent, num_points=50):
    x = np.linspace(x0, x1, num_points)
    exp_scale = np.linspace(0, 1, num_points) ** exponent
    y = y0 + (y1 - y0) * exp_scale
    return x, y


def s_curve_interpolation(x0, y0, x1, y1, num_points=50):
    x = np.linspace(x0, x1, num_points)
    t = (x - x0) / (x1 - x0)
    s_curve = t * t * (3 - 2 * t)
    y = y0 + (y1 - y0) * s_curve
    return x, y


def inverted_s_curve_interpolation(x0, y0, x1, y1, num_points=100):
    x = np.linspace(x0, x1, num_points)
    t = (x - x0) / (x1 - x0)
    steepness = 2.5
    p1y = 1 - steepness / 10
    p2y = steepness / 10
    bezier = (1 - t) ** 3 * 0 + 3 * (1 - t) ** 2 * t * p1y + 3 * (1 - t) * t ** 2 * p2y + t ** 3 * 1
    y = y0 + (y1 - y0) * bezier
    return x, y


def constant_interpolation(x0, y0, x1, y1, num_points=2):
    return [x0, x1], [y0, y0]


def y_to_position(y):
    if y > 0.0:
        y = 0.0
    elif y < -200.0:
        y = -200.0
    return np.interp(y, Y_VALUES, Y_POSITIONS)


# Shape name -> interpolator
SHAPE_INTERPOLATORS = {
    "Linear": lambda x0, y0, x1, y1: linear_interpolation(x0, y0, x1, y1),
    "Log1": lambda x0, y0, x1, y1: logarithmic_interpolation(x0, y0, x1, y1, base=3.5),
    "Log2": lambda x0, y0, x1, y1: logarithmic_interpolation(x0, y0, x1, y1, base=10),
    "Log3": lambda x0, y0, x1, y1: logarithmic_interpolation(x0, y0, x1, y1, base=30),
    "Exp1": lambda x0, y0, x1, y1: exponential_interpolation(x0, y0, x1, y1, exponent=1.3),
    "Exp2": lambda x0, y0, x1, y1: exponential_interpolation(x0, y0, x1, y1, exponent=2),
    "Exp3": lambda x0, y0, x1, y1: exponential_interpolation(x0, y0, x1, y1, exponent=4),
    "SCurve": lambda x0, y0, x1, y1: s_curve_interpolation(x0, y0, x1, y1),
    "InvertedSCurve": lambda x0, y0, x1, y1: inverted_s_curve_interpolation(x0, y0, x1, y1),
    "Constant": lambda x0, y0, x1, y1: constant_interpolation(x0, y0, x1, y1),
}

COLOR_MAPPING = {
    "VolumeWetGameUsage": "#c98036",
    "VolumeWetUserUsage": "#7c4d1d",
    "VolumeDryUsage": "#da2121",
    "LowPassFilterUsage": "#0080ff",
    "HighPassFilterUsage": "#30bffd",
    "SpreadUsage": "#8bd100",
    "FocusUsage": "#639400",
    "ObstructionVolumeUsage": "#c97a3c",
    "ObstructionLPFUsage": "#c97a3c",
    "ObstructionHPFUsage": "#e8a878",
    "OcclusionVolumeUsage": "#7c5fbe",
    "OcclusionLPFUsage": "#7c5fbe",
    "OcclusionHPFUsage": "#a497d4",
    "DiffractionVolumeUsage": "#bf5894",
    "DiffractionLPFUsage": "#bf5894",
    "DiffractionHPFUsage": "#d289b8",
    "TransmissionVolumeUsage": "#3848bc",
    "TransmissionLPFUsage": "#3848bc",
    "TransmissionHPFUsage": "#6c80df",
}

# Curve types whose Y range is [0, 100]. Everything else is dB in [-200, 0].
POSITIVE_CURVES = {
    "LowPassFilterUsage", "HighPassFilterUsage", "SpreadUsage", "FocusUsage",
    "ObstructionLPFUsage", "ObstructionHPFUsage",
    "OcclusionLPFUsage", "OcclusionHPFUsage",
    "DiffractionLPFUsage", "DiffractionHPFUsage",
    "TransmissionLPFUsage", "TransmissionHPFUsage",
}


class ChangeValueButton:
    """Clickable icon, used as the +/- nudge buttons on each AttenuationPoint row."""

    def __init__(self, master, image_path, size=(25, 25), command=None):
        self.label = ctk.CTkLabel(master, image=get_icon(image_path, size), text="")
        if command:
            self.label.bind('<Button-1>', lambda event: command())

    def grid(self, **kwargs):
        self.label.grid(**kwargs)

    def destroy(self):
        self.label.destroy()

    def grid_forget(self):
        self.label.grid_forget()


class AttenuationPoint:
    # (attr_name, icon, size, axis, delta, column, sticky)
    BUTTON_SPECS = [
        ('x_decrease_button_large', 'minus', 17, 'x', -10, 2, 'e'),
        ('x_decrease_button_small', 'minus', 10, 'x', -1, 3, 'e'),
        ('x_increase_button_small', 'plus', 10, 'x', 1, 5, 'w'),
        ('x_increase_button_large', 'plus', 17, 'x', 10, 6, 'w'),
        ('y_decrease_button_large', 'minus', 17, 'y', -10, 8, 'e'),
        ('y_decrease_button_small', 'minus', 10, 'y', -1, 9, 'e'),
        ('y_increase_button_small', 'plus', 10, 'y', 1, 11, 'w'),
        ('y_increase_button_large', 'plus', 17, 'y', 10, 13, 'w'),
    ]
    ABSOLUTE_X_MAX = 1_000_000.0

    def __init__(self, master, editor, x=0, y=0, on_delete=lambda index: None, index=0, on_change=lambda: None):

        self.editor = editor
        self.x = ctk.StringVar(value=x)
        self.y = ctk.StringVar(value=y)
        self.on_delete = on_delete
        self.on_change_callback = on_change
        self.index = index

        # Snapshot of last validated value; used to restore the entry after a failed edit.
        self.previous_x_value = x
        self.previous_y_value = y

        # Absolute/relative toggle. Hidden on endpoints via _apply_endpoint_visibility.
        self.is_absolute = ctk.BooleanVar(value=False)
        self.absolute_checkbox = ctk.CTkCheckBox(
            master, text="abs", variable=self.is_absolute, width=20,
            command=self._on_absolute_toggle,
        )
        self.absolute_checkbox.grid(row=index, column=0, sticky="w", padx=5, pady=5)

        # X entry + suffix label (% / abs) so the unit is visible without checking the checkbox.
        self.x_cell = ctk.CTkFrame(master, fg_color="transparent")
        self.x_entry = ctk.CTkEntry(self.x_cell, textvariable=self.x, width=70)
        self.unit_label = ctk.CTkLabel(
            self.x_cell, text="%", text_color="#7f7f7f", width=22, anchor="w",
        )
        self.x_entry.pack(side="left")
        self.unit_label.pack(side="left", padx=(2, 0))
        # Trace fires regardless of who flips is_absolute (checkbox, _enforce_absolute_prefix,
        # _create_point reuse), so the suffix never gets out of sync.
        self.is_absolute.trace_add("write", lambda *_: self.unit_label.configure(
            text="abs" if self.is_absolute.get() else "%"
        ))

        self.y_entry = ctk.CTkEntry(master, textvariable=self.y, width=80)
        self.delete_button = ctk.CTkButton(
            master, text="Delete", command=lambda: self.on_delete(self.index),
            fg_color="#404040", hover_color="#303030",
        )

        self.x_cell.grid(row=index, column=4, sticky="ew", padx=5, pady=5)
        self.y_entry.grid(row=index, column=10, sticky="ew", padx=5, pady=5)
        self.delete_button.grid(row=index, column=14, pady=5, sticky="e", padx=5)

        for attr, icon, size, axis, delta, col, sticky in self.BUTTON_SPECS:
            btn = ChangeValueButton(
                master, ICON_DIR / f"{icon}_icon.png", size=(size, size),
                command=lambda a=axis, d=delta: self.change_x_or_y_value(a, d),
            )
            btn.grid(row=index, column=col, sticky=sticky, padx=5, pady=5)
            setattr(self, attr, btn)

        self.shape_var = ctk.StringVar(value=shape_display_map["Linear"])
        self.shape_combo = ctk.CTkComboBox(
            master, values=list(shape_display_map.values()), variable=self.shape_var,
            state="readonly", command=lambda val: self.on_change_callback(),
        )
        self.shape_combo.grid(row=index, column=1, sticky="w", padx=5, pady=5)

        self.x_entry.bind('<FocusIn>', self.store_previous_x_value)
        self.x_entry.bind('<FocusOut>', self.validate_x_entry)
        self.x_entry.bind('<Return>', self.validate_x_entry)

        self.y_entry.bind('<FocusIn>', self.store_previous_y_value)
        self.y_entry.bind('<FocusOut>', self.validate_y_entry)
        self.y_entry.bind('<Return>', self.validate_y_entry)

    # Store as float (not the StringVar's string) so payload builders that read
    # previous_*_value send WAAPI a "number" type instead of "1.0" as a string.
    def store_previous_x_value(self, event=None):
        try:
            self.previous_x_value = float(self.x.get())
        except (ValueError, ctk.TclError):
            self.previous_x_value = 0.0

    def store_previous_y_value(self, event=None):
        try:
            self.previous_y_value = float(self.y.get())
        except (ValueError, ctk.TclError):
            self.previous_y_value = 0.0

    def _set_validated_x(self, new_value_raw):
        """
        Attempts to set a new X value after validation.
        Validation:
            * Convert to float; revert on failure.
            * Clamp [0, 100] for relative or [0, ABSOLUTE_X_MAX] for absolute.
            * Collision check only against same-type neighbors (different units don't compete).
        Returns True if the value was successfully set, False otherwise.
        """
        try:
            new_value_float = float(new_value_raw)
        except (ValueError, TypeError):
            self.x.set(self.previous_x_value)
            return False

        upper_clamp = self.ABSOLUTE_X_MAX if self.is_absolute.get() else 100.0
        clamped_value = max(0.0, min(upper_clamp, new_value_float))

        # Collision check against same-type neighbors (skipped for endpoints, which are locked).
        is_endpoint = (self.index == 0 or self.index == len(self.editor.active_points) - 1)
        if not is_endpoint:
            prev_x = self.get_prev_same_type_x()
            next_x = self.get_next_same_type_x()
            if (next_x is not None and clamped_value >= next_x) or \
                    (prev_x is not None and clamped_value <= prev_x):
                self.x.set(f"{self.previous_x_value:.3f}")
                self.on_change_callback()
                return False

        self.x.set(f"{clamped_value:.3f}")
        self.previous_x_value = clamped_value
        self.on_change_callback()
        return True

    def _set_validated_y(self, new_value_raw):
        """
        Attempts to set a new Y value after validation.
        Validation includes: conversion to float and clamping
        depending on the type of attenuation curve.
        Returns True if the value was successfully set, False otherwise.
        """

        try:
            new_value_float = float(new_value_raw)
        except (ValueError, TypeError):
            self.y.set(self.previous_y_value)
            return False

        # POSITIVE_CURVES (LPF/HPF/Spread/Focus + spatial LPF/HPF) → [0, 100].
        # Everything else (Volume curves incl. spatial Volume) → [-200, 0] dB.
        att_label = self.editor.att_var_string.get()
        curve_type = attenuation_map.get(att_label, "")
        if curve_type in POSITIVE_CURVES:
            clamped_value = max(0.0, min(100.0, new_value_float))
        else:
            clamped_value = max(-200.0, min(0.0, new_value_float))

        self.y.set(f"{clamped_value:.3f}")
        self.previous_y_value = clamped_value
        self.on_change_callback()
        return True

    def validate_x_entry(self, event):
        self._set_validated_x(self.x_entry.get())

    def validate_y_entry(self, event):
        self._set_validated_y(self.y_entry.get())

    def change_x_or_y_value(self, axis, value):
        if axis == 'x':
            current = float(self.x.get())
            new = current + value
            # Boundaries from same-type neighbors only; different-type neighbors don't compete.
            prev_x = self.get_prev_same_type_x()
            next_x = self.get_next_same_type_x()
            lower = prev_x if prev_x is not None else 0.0
            upper = next_x if next_x is not None else (
                self.ABSOLUTE_X_MAX if self.is_absolute.get() else 100.0
            )
            if new <= lower or new >= upper:
                return
            self._set_validated_x(new)
        elif axis == 'y':
            current = float(self.y.get())
            new = current + value
            self._set_validated_y(new)

    def get_prev_same_type_x(self):
        """X of nearest previous point with the same is_absolute as self, or None."""
        my_abs = self.is_absolute.get()
        for i in range(self.index - 1, -1, -1):
            pt = self.editor.active_points[i]
            if pt.is_absolute.get() == my_abs:
                try:
                    return float(pt.x.get())
                except (ValueError, ctk.TclError):
                    return None
        return None

    def get_next_same_type_x(self):
        """X of nearest next point with the same is_absolute as self, or None."""
        my_abs = self.is_absolute.get()
        for i in range(self.index + 1, len(self.editor.active_points)):
            pt = self.editor.active_points[i]
            if pt.is_absolute.get() == my_abs:
                try:
                    return float(pt.x.get())
                except (ValueError, ctk.TclError):
                    return None
        return None

    def _on_absolute_toggle(self):
        self.editor._enforce_absolute_prefix(self)
        self.on_change_callback()

    def _value_buttons(self):
        """All +/- buttons defined by BUTTON_SPECS, in declaration order."""
        return [getattr(self, attr) for attr, *_ in self.BUTTON_SPECS]

    def destroy(self):
        self.delete_button.destroy()
        self.x_cell.destroy()  # destroys x_entry + unit_label (its children)
        self.y_entry.destroy()
        self.shape_combo.destroy()
        self.absolute_checkbox.destroy()
        for btn in self._value_buttons():
            btn.destroy()

    def grid_forget(self):
        """
        Hide all of this point's widgets, but only if they're currently managed by grid.
        Safely ignores any widgets that have been destroyed.
        """
        widgets = [self.absolute_checkbox, self.shape_combo, self.x_cell, self.y_entry, self.delete_button]
        widgets += [btn.label for btn in self._value_buttons()]
        for w in widgets:
            try:
                if w.winfo_manager() == 'grid':
                    w.grid_forget()
            except Exception:
                # widget may have been destroyed or never gridded
                continue

    def regrid_row(self, row: int):
        self.grid_forget()
        self.absolute_checkbox.grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.shape_combo.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        self.x_cell.grid(row=row, column=4, sticky="ew", padx=5, pady=5)
        self.y_entry.grid(row=row, column=10, sticky="ew", padx=5, pady=5)
        self.delete_button.grid(row=row, column=14, sticky="e", padx=5, pady=5)
        for attr, _icon, _size, _axis, _delta, col, sticky in self.BUTTON_SPECS:
            getattr(self, attr).grid(row=row, column=col, sticky=sticky, padx=5, pady=5)


class AttenuationCurveEditor:
    def __init__(self, master):
        self.master = master
        self.MAX_ROWS = 20
        self.row_pool: list[AttenuationPoint] = []
        self.active_points: list[AttenuationPoint] = []
        self.max_x_values = {}
        self.selected_att = ""
        self.project_name = ""
        self.client = None  # set by _connect_to_wwise
        self.current_max_x = 100
        self._init_ui()

    def _init_ui(self):
        self.graph_display_status = 'no_att_selected'
        self._build_top_controls()
        self._build_points_pool()
        self._build_graph()
        self._build_info_frame()
        self._connect_to_wwise()

    def _build_top_controls(self):
        """Curve type combo + Get/Set buttons + X/Y headers (headers stay hidden until a curve loads)."""
        self.att_var_string = ctk.StringVar(value="Volume")
        self.curve_type_combo = ctk.CTkComboBox(
            self.master,
            state="readonly",
            variable=self.att_var_string,
            values=list(attenuation_map.keys()),
        )
        self.curve_type_combo.grid(row=1, column=0, pady=5, sticky="w", padx=12)

        self.x_header_label = ctk.CTkLabel(self.master, text="X")
        self.y_header_label = ctk.CTkLabel(self.master, text="Y")
        self.set_attenuation_button = ctk.CTkButton(
            self.master, text="Set Attenuation!", command=self.set_attenuation,
            fg_color="#404040", hover_color="#303030",
        )
        self.get_attenuation_button = ctk.CTkButton(
            self.master, text="Get Attenuation!", command=self.get_attenuation,
            fg_color="#404040", hover_color="#303030",
        )
        self.get_attenuation_button.grid(row=0, column=0, pady=5, padx=12, sticky="w")

    def _build_points_pool(self):
        """Scrollable frame + pre-allocate MAX_ROWS AttenuationPoint widgets, all hidden initially."""
        self.active_points_frame = ctk.CTkScrollableFrame(self.master, width=745, height=180)
        self.active_points_frame.grid(row=2, column=0, columnspan=16, sticky="nsew")
        for i in range(self.MAX_ROWS):
            pt = AttenuationPoint(
                self.active_points_frame, self,
                x=0, y=0,
                on_delete=lambda idx=i: self.delete_point(idx),
                index=i,
                on_change=self.update_graph,
            )
            pt.grid_forget()
            self.row_pool.append(pt)

    def _build_graph(self):
        """Matplotlib figure + canvas; the empty-state render is done by update_graph()."""
        self.fig, self.ax = plt.subplots(figsize=(5, 2))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.widget = self.canvas.get_tk_widget()
        self.widget.grid(row=3, column=0, columnspan=16, pady=10, sticky="ew")

        self.update_graph()

        self.ax.tick_params(axis='x', colors='#9f9f9f')
        self.ax.tick_params(axis='y', colors='#9f9f9f')
        self.ax.xaxis.label.set_color('#9f9f9f')
        self.ax.yaxis.label.set_color('#9f9f9f')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#9f9f9f')

    def _build_info_frame(self):
        """Bottom strip — connection status / project name lives here."""
        self.info_frame = ctk.CTkFrame(self.master)
        self.info_frame.grid(row=4, column=0, columnspan=16, sticky="ew")
        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=1)

    def _connect_to_wwise(self):
        """Connect to Wwise and populate the status label."""
        self.client = None
        text = "Cannot connect to Wwise"
        text_color = "#FF0000"
        if wwise_is_reachable():
            try:
                self.client = WaapiClient()
                self.project_name = self.client.call("ak.wwise.core.getProjectInfo")['name']
                text = str(self.project_name)
                text_color = "#4ade80"
            except Exception:
                logger.exception("Failed to connect to Wwise")
                self.client = None
        self.connection_status_label = ctk.CTkLabel(self.info_frame, text=text, text_color=text_color)
        self.connection_status_label.grid(row=0, column=0, sticky="w", padx=12)

    def show_controls(self):
        self.x_header_label.grid(row=1, column=4, pady=5)
        self.y_header_label.grid(row=1, column=12, pady=5)
        self.set_attenuation_button.grid(row=0, column=15, pady=5, padx=21, sticky="e")

    def hide_controls(self):
        self.x_header_label.grid_forget()
        self.y_header_label.grid_forget()
        self.set_attenuation_button.grid_forget()

    @staticmethod
    def _apply_endpoint_visibility(pt, is_first, is_last):
        """Endpoints can't be moved off their X position, can't be deleted, can't be made absolute."""
        if is_first or is_last:
            pt.delete_button.grid_forget()
            pt.absolute_checkbox.grid_forget()
        # Last point: locked at right boundary -> hide X- buttons
        if is_last:
            pt.x_decrease_button_small.grid_forget()
            pt.x_decrease_button_large.grid_forget()
        # First point: locked at left boundary -> hide X+ buttons
        if is_first:
            pt.x_increase_button_small.grid_forget()
            pt.x_increase_button_large.grid_forget()

    def sort_points(self):
        self.active_points.sort(key=lambda p: float(p.x.get()))
        n = len(self.active_points)
        for i, pt in enumerate(self.active_points):
            pt.index = i
            pt.regrid_row(i)
            self._apply_endpoint_visibility(pt, is_first=(i == 0), is_last=(i == n - 1))

    def _convert_x_to_match_type(self, pt):
        """
        Convert pt.x between percent and absolute units to match pt.is_absolute.
        Called right after the BooleanVar flips, so pt.x still holds the OLD-type value.
        Result is clamped to the type's valid range.
        """
        max_x = self.current_max_x or 100
        if max_x <= 0:
            return
        try:
            cur_x = float(pt.x.get())
        except (ValueError, ctk.TclError):
            return
        if pt.is_absolute.get():
            # was %, now absolute units
            new_x = cur_x * max_x / 100.0
            new_x = max(0.0, min(pt.ABSOLUTE_X_MAX, new_x))
        else:
            # was absolute, now %
            new_x = (cur_x / max_x) * 100.0
            new_x = max(0.0, min(100.0, new_x))
        pt.x.set(f"{new_x:.3f}")
        pt.previous_x_value = new_x

    def _enforce_absolute_prefix(self, toggled_pt):
        """
        Absolute middle points must form a contiguous prefix:
            [rel(locked), abs, abs, rel, ..., rel(locked)]
        - Checking point N  -> also check all earlier middle points.
        - Unchecking point N -> also uncheck all later middle points.
        Endpoints (first/last) are always relative and ignored.
        Each point whose state changes also has its X value converted between % and absolute units.
        """
        middle_pts = self.active_points[1:-1]
        if toggled_pt not in middle_pts:
            return

        # Toggled point's BooleanVar already flipped — convert its X to match the new type.
        self._convert_x_to_match_type(toggled_pt)

        idx = middle_pts.index(toggled_pt)
        if toggled_pt.is_absolute.get():
            for pt in middle_pts[:idx]:
                if not pt.is_absolute.get():
                    pt.is_absolute.set(True)
                    self._convert_x_to_match_type(pt)
        else:
            for pt in middle_pts[idx + 1:]:
                if pt.is_absolute.get():
                    pt.is_absolute.set(False)
                    self._convert_x_to_match_type(pt)

    def _create_point(self, x: float, y: float, shape_key: str = "Linear") -> AttenuationPoint:
        idx = len(self.active_points)
        if idx >= self.MAX_ROWS:
            return None  # too many points

        pt = self.row_pool[idx]
        pt.x.set(f"{x:.3f}")
        pt.y.set(f"{y:.3f}")
        pt.previous_x_value = x
        pt.previous_y_value = y
        pt.shape_var.set(shape_display_map.get(shape_key, shape_display_map["Linear"]))
        pt.is_absolute.set(False)  # pool widgets are reused — always start as relative
        pt.regrid_row(idx)
        self.active_points.append(pt)
        return pt

    def delete_point(self, index):
        # Endpoints (first/last) are locked.
        if index == 0 or index == len(self.active_points) - 1:
            return
        pt = self.active_points.pop(index)
        pt.grid_forget()
        self.sort_points()
        self.update_graph()

    def _load_max_x_values(self):
        # max_x = the attenuation's RadiusMax: every curve's X domain is [0, RadiusMax],
        # and Wwise rejects a Set whose last endpoint X != RadiusMax ("invalid endpoints").
        # No try/except here: caller (set_attenuation) wraps the whole flow.
        self.max_x_values.clear()
        selected = self.client.call("ak.wwise.ui.getSelectedObjects", {}, options={"return": ["id"]})['objects']
        ids = [obj['id'] for obj in selected]
        if not ids:
            return
        result = self.client.call(
            "ak.wwise.core.object.get",
            {"from": {"id": ids}},
            options={"return": ["id", "@RadiusMax"]},
        )['return']
        for entry in result:
            self.max_x_values[entry['id']] = entry.get('@RadiusMax', 100)

    def update_graph(self, event=None):
        if not self.active_points or self.graph_display_status in ('no_points', 'no_att_selected'):
            self.ax.cla()
            self.ax.text(
                0.5, 0.5,
                "No Attenuation Loaded",
                fontsize=24,
                color='#9f9f9f',
                ha='center', va='center',
            )
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.ax.set_facecolor('#2b2b2b')
            self.fig.patch.set_facecolor('#333333')
            self.canvas.draw()
            return

        max_x = self.current_max_x
        # Absolute points use literal X; relative points are rescaled from [0,100] to [0,max_x].
        x_vals = [self._final_x_for_object(pt, max_x) for pt in self.active_points]
        y_vals = [float(pt.y.get()) for pt in self.active_points]
        shapes = [display_to_shape[pt.shape_var.get()] for pt in self.active_points]
        # Extend the chart's X range if any absolute point overshoots max_x.
        chart_max = max(max_x, max(x_vals)) if x_vals else max_x
        self.ax.cla()

        selected_display = self.att_var_string.get()
        selected_type = attenuation_map[selected_display]
        selected_color = COLOR_MAPPING.get(selected_type, "#000000")

        if selected_type in POSITIVE_CURVES:
            margin = 5
            ymin, ymax = 0, 100
            self.ax.set_ylim(ymin - margin, ymax + margin)
            self.ax.set_yticks(np.arange(0, 101, 10))
            y_vals_plot = y_vals
        else:
            margin = 0.05
            ymin, ymax = 0, 1
            self.ax.set_ylim(ymin - margin, ymax + margin)
            self.ax.set_yticks(Y_POSITIONS)
            self.ax.set_yticklabels([str(y) for y in Y_VALUES])
            y_vals_plot = [y_to_position(y) for y in y_vals]

        for i in range(len(x_vals) - 1):
            x0, y0 = x_vals[i], y_vals_plot[i]
            x1, y1 = x_vals[i + 1], y_vals_plot[i + 1]
            interp = SHAPE_INTERPOLATORS.get(shapes[i], SHAPE_INTERPOLATORS["Linear"])
            xi, yi = interp(x0, y0, x1, y1)
            self.ax.plot(xi, yi, marker='', color=selected_color)

        self.ax.plot(x_vals, y_vals_plot, 'o', color=selected_color)
        self.ax.grid(color='#3a3a3a')
        self.ax.set_facecolor('#2b2b2b')
        self.fig.patch.set_facecolor('#333333')
        if self.selected_att:
            self.ax.set_title(self.selected_att, color='#c8c3c3')

        # Pad the X range so endpoint markers aren't clipped at the axis edge.
        pad = chart_max * 0.05
        self.ax.set_xlim(-pad, chart_max + pad)

        # Explicit ticks so the last tick equals chart_max (matplotlib's auto-ticks round it).
        xticks = np.linspace(0, chart_max, num=6)
        self.ax.set_xticks(xticks)
        self.ax.set_xticklabels([str(int(t)) for t in xticks])

        self.canvas.draw()

    def _final_x_with_overflow(self, point, max_x):
        """
        Returns (final_x, overflow) for a point against a target attenuation's max_x.
            * relative point: final_x = ui_x * max_x / 100, overflow always False.
            * absolute point: final_x = ui_x, overflow True if ui_x > max_x.
        Reads from previous_x_value (float) — the entry's :.3f display loses precision
        that Wwise then rejects on Set.
        """
        ui_x = point.previous_x_value
        if point.is_absolute.get():
            return ui_x, ui_x > max_x
        return (ui_x / 100.0) * max_x, False

    def _final_x_for_object(self, point, max_x):
        final_x, _ = self._final_x_with_overflow(point, max_x)
        return final_x

    def _build_payload_for_object(self, max_x):
        """Build the WAAPI points payload for a single object."""
        payload = []
        for point in self.active_points:
            real_x = self._final_x_for_object(point, max_x)
            real_y = point.previous_y_value  # full precision, not the :.3f display
            shape_key = display_to_shape[point.shape_var.get()]
            payload.append({"x": real_x, "y": real_y, "shape": shape_key})
        return payload

    def _apply_to_objects(self, objects):
        """Send setAttenuationCurve for each object."""
        curve_type = attenuation_map[self.att_var_string.get()]
        for obj in objects:
            obj_id = obj['id']
            max_x = self.max_x_values.get(obj_id, 100)
            args = {
                "object": obj_id,
                "curveType": curve_type,
                "use": "Custom",
                "points": self._build_payload_for_object(max_x),
            }
            self.client.call("ak.wwise.core.object.setAttenuationCurve", args)

    def _check_object_conflict(self, obj):
        """
        Returns True if applying the curve to this object would produce a conflict:
            * an absolute point exceeds the object's max_x, or
            * the resulting X sequence is not strictly increasing.
        """
        max_x = self.max_x_values.get(obj['id'], 100)
        final_xs = []
        for point in self.active_points:
            final_x, overflow = self._final_x_with_overflow(point, max_x)
            if overflow:
                return True
            final_xs.append(final_x)
        return any(final_xs[i] >= final_xs[i + 1] for i in range(len(final_xs) - 1))

    def set_attenuation(self):
        if self.client is None:
            mb.showerror("Connection error", "Cannot reach Wwise. Make sure it's running with WAAPI enabled.",
                         parent=self.master)
            return
        try:
            self._load_max_x_values()
            selected = self.client.call(
                "ak.wwise.ui.getSelectedObjects",
                {},
                options={"return": ["id", "name"]},
            )['objects']

            # Pre-flight: split into valid vs conflicting
            valid_objects = []
            conflict_names = []
            for obj in selected:
                if self._check_object_conflict(obj):
                    conflict_names.append(obj.get('name', 'Unknown'))
                else:
                    valid_objects.append(obj)

            if conflict_names:
                self._show_conflict_modal(conflict_names, valid_objects, len(selected))
            else:
                self._apply_to_objects(selected)

        except Exception:
            logger.exception("Failed to apply attenuation curve")
            mb.showerror("Connection error", "Cannot reach Wwise. Make sure it's running with WAAPI enabled.",
                         parent=self.master)

    def _show_conflict_modal(self, conflict_names, valid_objects, total_count):
        """Warning dialog listing conflicts; user can apply to valid-only or cancel."""
        conflict_count = len(conflict_names)
        valid_count = len(valid_objects)

        MAX_LIST = 20
        shown = conflict_names[:MAX_LIST]
        overflow = conflict_count - len(shown)
        list_text = "\n".join(f"  • {name}" for name in shown)
        if overflow > 0:
            list_text += f"\n  ... and {overflow} more"

        base_info = (
            "In some of the selected attenuations, an absolute point is larger "
            "than the relative range of the target curve.\n\n"
            f"Conflicting attenuations ({conflict_count} of {total_count}):\n"
            f"{list_text}\n\n"
            "Tip: for best results the source attenuation (the one you're "
            "copying from) should be shorter than the target attenuations."
        )

        if valid_count == 0:
            mb.showwarning(
                "Conflicts detected",
                base_info + "\n\nNo valid attenuations to apply changes to.",
                parent=self.master,
            )
            return

        message = base_info + f"\n\nApply to {valid_count} valid attenuations?"
        if mb.askyesno("Conflicts detected", message, icon=mb.WARNING, parent=self.master):
            self._apply_to_objects(valid_objects)

    def get_attenuation(self):
        if self.client is None:
            mb.showerror("Connection error", "Cannot reach Wwise. Make sure it's running with WAAPI enabled.",
                         parent=self.master)
            return
        try:
            selected = self.client.call("ak.wwise.ui.getSelectedObjects", {},
                                        options={"return": ["id", "name"]})['objects']
            if not selected:
                self.hide_controls()
                return
            first_object = selected[0]
            first_object_id = first_object['id']
            first_object_name = first_object.get('name', 'Unknown')
            self.selected_att = first_object_name
            for pt in self.active_points:
                pt.grid_forget()
            self.active_points.clear()
            get_args = {"object": first_object_id, "curveType": attenuation_map[self.att_var_string.get()]}
            get_att = self.client.call("ak.wwise.core.object.getAttenuationCurve", get_args)
            points = get_att.get('points', [])

            if len(points) > self.MAX_ROWS:
                mb.showwarning(
                    "Too many points",
                    f"Curve has {len(points)} points, but the maximum supported is {self.MAX_ROWS}."
                )
                self.hide_controls()
                self.graph_display_status = 'no_points'
                self.update_graph()
                return

            if points:
                # Normalize the loaded curve's X to fill the UI's 0-100 range so the
                # locked endpoints land at 0 and 100. Set scales 100 back to RadiusMax.
                max_x_value = max(p['x'] for p in points)
                self.current_max_x = max_x_value
                for p in points:
                    scaled_x = (p['x'] / max_x_value) * 100
                    new_point = self._create_point(scaled_x, p['y'])
                    new_point.shape_var.set(shape_display_map[p.get('shape', 'Linear')])
                self.graph_display_status = 'points'
                self.show_controls()
            else:
                self.graph_display_status = 'no_points'
                self.hide_controls()
            self.update_graph()
            self.sort_points()  # also re-applies endpoint visibility (hides Delete on first/last)
        except Exception:
            logger.exception("Failed to read attenuation curve")
            mb.showerror(
                "Read failed",
                "Couldn't read the attenuation curve. Check the selected object and WAAPI connection.",
                parent=self.master,
            )

    def close_connection(self):
        if self.client is None:
            return
        try:
            self.client.disconnect()
        except Exception:
            logger.exception("Failed to disconnect from Wwise")


def main():
    setup_logging()
    app = ctk.CTk()
    app.resizable(False, False)
    app.attributes("-topmost", True)
    app.title("Attenuation Batch Edit")

    editor = AttenuationCurveEditor(app)

    def on_closing():
        editor.close_connection()
        plt.close('all')
        app.quit()
        app.after(50, app.destroy)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()