import customtkinter as ctk
from waapi import WaapiClient
import traceback
from customtkinter import CTkImage
from PIL import Image
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('TkAgg')    # use Tkinter backend 
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("Dark")

ICON_DIR = Path(__file__).resolve().parent / "Icons"

# Dictionary for Attenuation type label mapping 
attenuation_map = {
    "Volume": "VolumeDryUsage",
    "Auxiliary send volumes (Game-defined)": "VolumeWetGameUsage",
    "Auxiliary send volumes (User-defined)": "VolumeWetUserUsage",
    "Low-pass filter": "LowPassFilterUsage",
    "High-pass filter": "HighPassFilterUsage",
    "Spread": "SpreadUsage",
    "Focus": "FocusUsage"
}

shape_display_map = {
    "Constant":        "Constant",
    "Linear":          "Linear",
    "Log3":            "Logarithmic Base 3",
    "Log2":            "Sine (Constant Power Fade In)",
    "Log1":            "Logarithmic (Base 1.41)",
    "InvertedSCurve":  "Inverted S-Curve",
    "SCurve":          "S-Curve",
    "Exp1":            "Exponential (Base 1.41)",
    "Exp2":            "Sine (Constant Power Fade Out)",
    "Exp3":            "Exponential Base 3"
}
display_to_shape = {disp:key for key,disp in shape_display_map.items()}

# Matplot lib Interpolation functions
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

def custom_scurve_interpolation(x0, y0, x1, y1, num_points=100):
    x = np.linspace(x0, x1, num_points)
    t = (x - x0) / (x1 - x0)
    steepness = 2.5
    p1y = 1 - steepness/10
    p2y = steepness/10
    bezier = (1-t)**3 * 0 + 3*(1-t)**2*t*p1y + 3*(1-t)*t**2*p2y + t**3*1
    y = y0 + (y1 - y0) * bezier
    return x, y

def constant_interpolation(x0, y0, x1, y1, num_points=2):
    return [x0, x1], [y0, y0]

def y_to_position(y):
    y_values = [-200.0, -18.1, -12.0, -8.5, -6.0, -4.1, -2.5, -1.2, 0.0]
    positions = np.linspace(0.0, 1.0, num=9).tolist()
    if y > 0.0:
        y = 0.0
    elif y < -200.0:
        y = -200.0
    return np.interp(y, y_values, positions)


# change value button class - CTkLabel for images
class ChangeValueButton:
    def __init__(self, master, image_path, size=(25, 25), command=None):
        
        self.master = master
        self.image_path = image_path
        self.size = size
        self.command = command
        self.load_image()
        self.label = ctk.CTkLabel(master, image=self.photo_image, text="")
        if command:
            self.label.bind('<Button-1>', lambda event: command())
    
    def load_image(self):
       
        
        image = Image.open(self.image_path)
        self.photo_image = CTkImage(light_image=image, dark_image=image, size=self.size)
    
    def grid(self, **kwargs):
        self.label.grid(**kwargs)
    
    def destroy(self):
        self.label.destroy()
    
    def grid_forget(self):
        self.label.grid_forget()



class AttenuationPoint:
    def __init__(self, master, editor, x=0, y=0, on_delete=lambda index: None, index=0, on_change=lambda: None):

        self.editor = editor
        self.x = ctk.StringVar(value=x)
        self.y = ctk.StringVar(value=y)
        self.on_delete = on_delete
        self.on_change_callback = on_change 
        self.index = index

        # --- storing previos x/y vales ---
        # to restore values ​​in case of failed validation
        self.previous_x_value = x
        self.previous_y_value = y

        # --- UI Elements ---
        self.x_entry = ctk.CTkEntry(master, textvariable=self.x, width=80)
        self.y_entry = ctk.CTkEntry(master, textvariable=self.y, width=80)
        self.delete_button = ctk.CTkButton(master, text="Delete", command=lambda: self.on_delete(self.index),
                                           fg_color="#404040", hover_color="#303030")

        # Grid for main elements
        self.x_entry.grid(row=index, column=3, sticky="ew", padx=5, pady=5)
        self.y_entry.grid(row=index, column=9, sticky="ew", padx=5, pady=5) 
        self.delete_button.grid(row=index, column=13, pady=5, sticky="e", padx=5)

        #  +/- Buttons 
        self.X_decrease_button_large = ChangeValueButton(master, ICON_DIR / "minus_icon.png", size=(17, 17), command=lambda: self.change_x_or_y_value('x', -10))
        self.X_decrease_button_large.grid(row=index, column=1, sticky="e", padx=(5,0), pady=5) 
        self.X_decrease_button_small = ChangeValueButton(master, ICON_DIR / "minus_icon.png", size=(10, 10), command=lambda: self.change_x_or_y_value('x', -1))
        self.X_decrease_button_small.grid(row=index, column=2, sticky="e", padx=0, pady=5)
        self.X_increase_button_small = ChangeValueButton(master, ICON_DIR / "plus_icon.png", size=(10, 10), command=lambda: self.change_x_or_y_value('x', 1))
        self.X_increase_button_small.grid(row=index, column=4, sticky="w", padx=0, pady=5)
        self.X_increase_button_large = ChangeValueButton(master, ICON_DIR / "plus_icon.png", size=(17, 17), command=lambda: self.change_x_or_y_value('x', 10))
        self.X_increase_button_large.grid(row=index, column=5, sticky="w", padx=(0,5), pady=5)

        self.Y_decrease_button_large = ChangeValueButton(master, ICON_DIR / "minus_icon.png", size=(17, 17), command=lambda: self.change_x_or_y_value('y', -10))
        self.Y_decrease_button_large.grid(row=index, column=7, sticky="e", padx=(5,0), pady=5)
        self.Y_decrease_button_small = ChangeValueButton(master, ICON_DIR / "minus_icon.png", size=(10, 10), command=lambda: self.change_x_or_y_value('y', -1))
        self.Y_decrease_button_small.grid(row=index, column=8, sticky="e", padx=0, pady=5)
        self.Y_increase_button_small = ChangeValueButton(master, ICON_DIR / "plus_icon.png", size=(10, 10), command=lambda: self.change_x_or_y_value('y', 1))
        self.Y_increase_button_small.grid(row=index, column=10, sticky="w", padx=0, pady=5)
        self.Y_increase_button_large = ChangeValueButton(master, ICON_DIR / "plus_icon.png", size=(17, 17), command=lambda: self.change_x_or_y_value('y', 10))
        self.Y_increase_button_large.grid(row=index, column=12, sticky="w", padx=(0,5), pady=5)

        # ComboBox 
        self.att_curve_string = ctk.StringVar(value=shape_display_map["Linear"])
        self.att_type_combo = ctk.CTkComboBox(
            master, values=list(shape_display_map.values()), variable=self.att_curve_string,
            state="readonly", command=lambda val: self.on_change_callback() # Użycie nowego callbacku
        )
        self.att_type_combo.grid(row=index, column=0, sticky="w", padx=5, pady=5)


        # --- Bindings for validation ---
        self.x_entry.bind('<FocusIn>', self.store_previous_x_value)
        self.x_entry.bind('<FocusOut>', self.validate_x_entry)
        self.x_entry.bind('<Return>', self.validate_x_entry)

        self.y_entry.bind('<FocusIn>', self.store_previous_y_value)
        self.y_entry.bind('<FocusOut>', self.validate_y_entry)
        self.y_entry.bind('<Return>', self.validate_y_entry)

    # --- Helper methods for storing previous valuesRetry ---
    def store_previous_x_value(self, event=None): 
        """Stores the current X value before attempting to change it."""
        try:
            self.previous_x_value = self.x.get()
        except (ValueError, ctk.TclError): 
             self.previous_x_value = 0.0 

    def store_previous_y_value(self, event=None): 
        """Stores the current Y value before attempting to change it."""
        try:
            self.previous_y_value = self.y.get()
        except (ValueError, ctk.TclError):
             self.previous_y_value = 0.0

    # --- CENTRALNE METODY WALIDACJI ---

    def _set_validated_x(self, new_value_raw):
        """
        Attempts to set a new X value after validation.
        Validation includes: conversion to float, clamping [0, 100],
        and checking for collisions with neighboring points.
        Returns True if the value was successfully set, False otherwise.
        """
        try:
            new_value_float = float(new_value_raw)
        except (ValueError, TypeError):
            self.x.set(self.previous_x_value)
            return False

        #[0, 100] Clamp
        clamped_value = max(0.0, min(100.0, new_value_float))

       
        # Collision check beetwen nearest points  
        next_point_x = self.get_next_point_x()
        prev_point_x = self.get_prev_point_x()

        # Only perform this check if we’re not an endpoint (which have fixed X = 0 or 100)
        # We assume that endpoints’ X values shouldn’t be changed by the user
        # (If endpoints can be adjusted, this logic will need to be updated)

        is_endpoint = (self.index == 0 or self.index == len(self.editor.points) - 1)
        if not is_endpoint:
            #  Collision chect
            if (next_point_x is not None and clamped_value >= next_point_x) or \
               (prev_point_x is not None and clamped_value <= prev_point_x):
                self.x.set(self.previous_x_value) # Restore if collision
                self.on_change_callback() # Call the callback even after reverting

                return False

        # If validation passed successfully:
        self.x.set(clamped_value)
        self.previous_x_value = clamped_value # Update the stored valid value

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
            self.y.set(self.previous_y_value) # Restore the previous value in case of a conversion error
            return False

        # Clamping based on the curve type
        zero_max = {
            "Volume",
            "Auxiliary send volumes (Game-defined)",
            "Auxiliary send volumes (User-defined)"
        }
        att_label = self.editor.att_var_string.get() # Retrieve the type from the editor

        if att_label in zero_max:
            clamped_value = max(-200.0, min(0.0, new_value_float))
        else:
            clamped_value = max(0.0, min(100.0, new_value_float))

        # Set the value
        self.y.set(clamped_value)
        self.previous_y_value = clamped_value # Update the stored valid value
        self.on_change_callback()
        return True

    # --- Methods invoked by the UI---

    def validate_x_entry(self, event):
        """Called after editing the X field."""
        self._set_validated_x(self.x_entry.get())

    def validate_y_entry(self, event):
        """Called after editing the Y field."""
        self._set_validated_y(self.y_entry.get())

    def change_x_or_y_value(self, axis, value):
        """Wywoływane po kliknięciu przycisków +/-."""
        if axis == 'x':
            # Read the current value *before* attempting the change
            # This is important if a previous set attempt failed
            # but the variable may have been temporarily altered by text input.
            # It’s safer to use the stored `previous_x_value` as the base.
            # Although retrieving via self.x.get() should work after refactoring.
            current_value = float(self.x.get())  # Get the current value from the DoubleVar
            new_value = current_value + value
            self._set_validated_x(new_value)
        elif axis == 'y':
            current_value = float(self.y.get())
            new_value = current_value + value
            self._set_validated_y(new_value)

    
    def get_next_point_x(self):
        next_index = self.index + 1
        if next_index < len(self.editor.points):
            try:
                 return float(self.editor.points[next_index].x.get())
            except (ValueError, ctk.TclError):
                 return None 
        return None

    def get_prev_point_x(self):
        prev_index = self.index - 1
        if prev_index >= 0:
            try:
                 return float(self.editor.points[prev_index].x.get())
            except (ValueError, ctk.TclError):
                 return None
        return None

    def destroy(self):
        self.delete_button.destroy()
        self.x_entry.destroy()
        self.y_entry.destroy()
        self.att_type_combo.destroy()
        self.X_decrease_button_large.destroy()
        self.X_decrease_button_small.destroy()
        self.X_increase_button_large.destroy()
        self.X_increase_button_small.destroy()
        self.Y_decrease_button_small.destroy()
        self.Y_decrease_button_large.destroy()
        self.Y_increase_button_large.destroy()
        self.Y_increase_button_small.destroy()


# Curve Editor class
class AttenuationCurveEditor:
    def __init__(self, master):
        self.master = master
        self.points = []
        self.max_x_values = {}
        self.selected_att = ""
        self.project_name = ""
        self.client = WaapiClient()
        self.init_ui()

    def init_ui(self):
        
        self.att_var_string = ctk.StringVar(value="Volume")
        self.att_type_combo = ctk.CTkComboBox(
            self.master,
            state="readonly",
            variable=self.att_var_string,
            values=list(attenuation_map.keys())
            
        )
        self.att_type_combo.grid(row=1, column=0, pady=5, sticky="w", padx=12)
        self.graph_display_status = 'no_att_selected'
        
        self.get_attenuation_X_label = ctk.CTkLabel(self.master, text="X %")
        self.get_attenuation_Y_label = ctk.CTkLabel(self.master, text="Y")
        # self.add_point_button = ctk.CTkButton(self.master, text="Add Point", command=self.add_point,
        #                                       fg_color="#404040", hover_color="#303030")
        self.set_attenuation_button = ctk.CTkButton(self.master, text="Set Attenuation!", command=self.set_attenuation,
                                                    fg_color="#404040", hover_color="#303030")
        self.get_attenuation_button = ctk.CTkButton(self.master, text="Get Attenuation!", command=self.get_attenuation,
                                                    fg_color="#404040", hover_color="#303030")
        self.get_attenuation_button.grid(row=0, column=0, pady=5, padx=12, sticky="w")
        
        # scrollable frame for points - height set to fit 6 rows
        self.points_frame = ctk.CTkScrollableFrame(self.master, width=670, height=180)
        self.points_frame.grid(row=2, column=0, columnspan=15, sticky="nsew")
        
        self.fig, self.ax = plt.subplots(figsize=(5, 2))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.widget = self.canvas.get_tk_widget()
        self.widget.grid(row=3, column=0, columnspan=15, pady=10, sticky="ew")

        self.ax.set_facecolor('#2b2b2b')
        self.fig.patch.set_facecolor('#333333')
        self.ax.grid(color='#3a3a3a')
        self.ax.set_title(self.selected_att, color='#db9951')
        self.ax.text(0.025, 0.435, "Select Attenuation Shareset", fontsize=19, color='#9f9f9f')
        self.update_graph()

        self.ax.tick_params(axis='x', colors='#9f9f9f')
        self.ax.tick_params(axis='y', colors='#9f9f9f')
        self.ax.xaxis.label.set_color('#9f9f9f')
        self.ax.yaxis.label.set_color('#9f9f9f')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#9f9f9f')

        self.info_frame = ctk.CTkFrame(self.master)
        self.info_frame.grid(row=4, column=0, columnspan=15, sticky="ew")

        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=1)

        try:
            print("Getting Wwise instance information:")
            result = self.client.call("ak.wwise.core.getProjectInfo")
            self.project_name = result['name']
            self.connection_status_label = ctk.CTkLabel(self.info_frame, text=str(self.project_name))
            self.connection_status_label.grid(row=0, column=0, sticky="w", padx = 12)
        except Exception as e:
            traceback.print_exc()
            print(str(e))
            self.connection_status_label = ctk.CTkLabel(self.info_frame, text="Cannot connect to Wwise")
            self.connection_status_label.grid(row=0, column=0, sticky="w", padx=5)


    def show_controls(self):
        self.get_attenuation_X_label.grid(row=1, column=3, pady=5)
        self.get_attenuation_Y_label.grid(row=1, column=11, pady=5)
        #self.add_point_button.grid(row=1, column=14, pady=5, padx=21, sticky="e")
        self.set_attenuation_button.grid(row=0, column=14, pady=5, padx=21, sticky="e")

    def hide_controls(self):
        self.get_attenuation_X_label.grid_forget()
        self.get_attenuation_Y_label.grid_forget()
        #self.add_point_button.grid_forget()
        self.set_attenuation_button.grid_forget()

    def sort_points(self):
        self.points.sort(key=lambda point: float(point.x.get()))
        for i, point in enumerate(self.points):
            point.index = i
            self.regrid_point(point, i)

            is_endpoint = (i == 0 or i == len(self.points) - 1)

            # Delete - hidden only on endpoints
            if is_endpoint:
                point.delete_button.grid_forget()
            else:
                # make sure it's visible
                point.delete_button.grid(row=i, column=13, sticky="e", padx=5, pady=5)

            # plus/minus at X - unbind on endpoints, bind on others
            for btn in (
                point.X_decrease_button_large,
                point.X_decrease_button_small,
                point.X_increase_button_small,
                point.X_increase_button_large
            ):
                # first clear old bindings
                btn.label.unbind('<Button-1>')
                if not is_endpoint:
                    # restore the binding to the original command
                    btn.label.bind('<Button-1>', lambda e, b=btn: b.command())

    def regrid_point(self, point, row):
        point.x_entry.grid_forget()
        point.y_entry.grid_forget()
        point.delete_button.grid_forget()
        point.att_type_combo.grid_forget()
        point.X_decrease_button_small.grid_forget()
        point.X_decrease_button_large.grid_forget()
        point.X_increase_button_large.grid_forget()
        point.X_increase_button_small.grid_forget()
        point.Y_decrease_button_small.grid_forget()
        point.Y_decrease_button_large.grid_forget()
        point.Y_increase_button_large.grid_forget()
        point.Y_increase_button_small.grid_forget()

        point.att_type_combo.grid(row=row, column=0, sticky="w", padx=5, pady=5)
        point.X_decrease_button_large.grid(row=row, column=1, sticky="e", padx=5, pady=5)
        point.X_decrease_button_small.grid(row=row, column=2, sticky="e", padx=5, pady=5)
        point.x_entry.grid(row=row, column=3, sticky="ew", padx=5, pady=5)
        point.X_increase_button_small.grid(row=row, column=4, sticky="w", padx=5, pady=5)
        point.X_increase_button_large.grid(row=row, column=5, sticky="w", padx=5, pady=5)
        point.Y_decrease_button_large.grid(row=row, column=7, sticky="e", padx=5, pady=5)
        point.Y_decrease_button_small.grid(row=row, column=8, sticky="e", padx=5, pady=5)
        point.y_entry.grid(row=row, column=9, sticky="ew", padx=5, pady=5)
        point.Y_increase_button_small.grid(row=row, column=10, sticky="w", padx=5, pady=5)
        point.Y_increase_button_large.grid(row=row, column=12, sticky="w", padx=5, pady=5)
        point.delete_button.grid(row=row, column=13, sticky="e", padx=5, pady=5)

    # def add_point(self):
    #     if len(self.points) > 1:
    #         first_point = self.points[0]
    #         last_point = self.points[-2]
    #         middle_x = float(first_point.x.get()) + float(last_point.x.get()) + 1
    #         middle_y = float(last_point.y.get())
    #         self._create_point(middle_x, middle_y)
    #     else:
    #         self._create_point(50, 0)

    def _create_point(self, x, y):
        index = len(self.points)
        #self.points_frame as the container for new points
        point = AttenuationPoint(self.points_frame, self, x, y, self.delete_point, index, self.update_graph)
        self.points.append(point)
        self.sort_points()
        self.update_graph()
        return point

    def delete_point(self, index):
        #Prevent deletion of endpoints
        if index == 0 or index == len(self.points) - 1:
            return

        #Delete the point
        self.points[index].destroy()
        del self.points[index]

        self.sort_points()
        self.update_graph()
        

    def get_highest_x_value(self):
        try:
            self.max_x_values.clear()
            selected = self.client.call("ak.wwise.ui.getSelectedObjects", {}, options={"return": ["id"]})['objects']
            for obj in selected:
                obj_id = obj['id']
                get_args = {"object": obj_id, "curveType": attenuation_map[self.att_var_string.get()]}
                get_att = self.client.call("ak.wwise.core.object.getAttenuationCurve", get_args)
                points = get_att.get('points', [])
                if points:
                    max_x = max(point['x'] for point in points)
                    self.max_x_values[obj_id] = max_x
        except Exception as e:
            traceback.print_exc()
            print(str(e))

    def update_graph(self, event=None):
        
        if not self.points or self.graph_display_status in ('no_points', 'no_att_selected'):
            self.ax.cla()
            
            self.ax.text(
                0.5, 0.5,
                "No Attenuation Loaded",
                fontsize=24,
                color='#9f9f9f',
                ha='center', va='center'
            )
            
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.ax.set_facecolor('#2b2b2b')
            self.fig.patch.set_facecolor('#333333')
            self.canvas.draw()
            return
        
        # Use the same max X from get_attenuation (fallback to 100)
        max_x = getattr(self, 'current_max_x', 100)
        x_vals = []
        y_vals = []
        shapes = [ display_to_shape[pt.att_curve_string.get()] for pt in self.points ]
        for point in self.points:
            x_vals.append(float(point.x.get()) * max_x / 100)
            y_vals.append(float(point.y.get()))
            shapes.append(point.att_curve_string.get())
        self.ax.cla()

        selected_display = self.att_var_string.get()
        selected_type = attenuation_map[selected_display]

        color_mapping = {
            "VolumeWetGameUsage": "#c98036",
            "VolumeWetUserUsage": "#7c4d1d",
            "VolumeDryUsage": "#da2121",
            "LowPassFilterUsage": "#0080ff",
            "HighPassFilterUsage": "#30bffd",
            "SpreadUsage": "#8bd100",
            "FocusUsage": "#639400"
        }
        selected_color = color_mapping.get(selected_type, "#000000")
        positive_curve = ["LowPassFilterUsage", "HighPassFilterUsage", "SpreadUsage", "FocusUsage"]
        is_positive_curve = selected_type in positive_curve
        if is_positive_curve:
            margin = 5
            ymin, ymax = 0, 100
            self.ax.set_ylim(ymin - margin, ymax + margin)
            self.ax.set_yticks(np.arange(0, 101, 10))
            y_vals_plot = y_vals
        else:
            margin = 0.05
            ymin, ymax = 0, 1
            self.ax.set_ylim(ymin - margin, ymax + margin)
            y_values = [-200.0, -18.1, -12.0, -8.5, -6.0, -4.1, -2.5, -1.2, 0.0]
            positions = np.linspace(0.0, 1.0, num=9).tolist()
            self.ax.set_yticks(positions)
            self.ax.set_yticklabels([str(y) for y in y_values])
            y_vals_plot = [y_to_position(y) for y in y_vals]

        for i in range(len(x_vals) - 1):
            x0, y0 = x_vals[i], y_vals_plot[i]
            x1, y1 = x_vals[i + 1], y_vals_plot[i + 1]
            shape = shapes[i]
            if shape == "Linear":
                xi, yi = linear_interpolation(x0, y0, x1, y1)
            elif shape == "Log1":
                xi, yi = logarithmic_interpolation(x0, y0, x1, y1, base=3.5)
            elif shape == "Log2":
                xi, yi = logarithmic_interpolation(x0, y0, x1, y1, base=10)
            elif shape == "Log3":
                xi, yi = logarithmic_interpolation(x0, y0, x1, y1, base=30)
            elif shape == "Exp1":
                xi, yi = exponential_interpolation(x0, y0, x1, y1, exponent=1.3)
            elif shape == "Exp2":
                xi, yi = exponential_interpolation(x0, y0, x1, y1, exponent=2)
            elif shape == "Exp3":
                xi, yi = exponential_interpolation(x0, y0, x1, y1, exponent=4)
            elif shape == "SCurve":
                xi, yi = s_curve_interpolation(x0, y0, x1, y1)
            elif shape == "InvertedSCurve":
                xi, yi = custom_scurve_interpolation(x0, y0, x1, y1)
            elif shape == "Constant":
                xi, yi = constant_interpolation(x0, y0, x1, y1)
            else:
                xi, yi = linear_interpolation(x0, y0, x1, y1)
            self.ax.plot(xi, yi, marker='', color=selected_color)

        self.ax.plot(x_vals, y_vals_plot, 'o', color=selected_color)
        self.ax.grid(color='#3a3a3a')
        self.ax.set_facecolor('#2b2b2b')
        self.fig.patch.set_facecolor('#333333')
        if self.selected_att:
            self.ax.set_title(self.selected_att, color='#c8c3c3')

        # Compute padding for X-axis (5% of max_x) and set range with padding
        pad = max_x * 0.05
        self.ax.set_xlim(-pad, max_x + pad)

        # Force X-axis ticks so last tick matches original max_x
        num_ticks = 6
        xticks = np.linspace(0, max_x, num=num_ticks)
        self.ax.set_xticks(xticks)
        self.ax.set_xticklabels([str(int(t)) for t in xticks])

        self.canvas.draw()

    def set_attenuation(self):
        # Retrieve the current maximum X values for the selected objects
        self.get_highest_x_value()
        try:
            # Retrieve the selected objects in Wwise
            selected = self.client.call(
                "ak.wwise.ui.getSelectedObjects",
                {},
                options={"return": ["id", "name"]}
            )['objects']
            
            for obj in selected:
                obj_id = obj['id']
                # Determine the actual maximum X (default to 100 if no data)
                max_x = self.max_x_values.get(obj_id, 100)
                
                # Prepare the list of points
                points_payload = []
                for point in self.points:
                    # Rescale X from [0–100] to [0–max_x]
                    real_x = float(point.x.get()) * max_x / 100
                    real_y = float(point.y.get())
                    # Convert UI name to the internal shape key
                    shape_key = display_to_shape[point.att_curve_string.get()]
                    points_payload.append({
                        "x": real_x,
                        "y": real_y,
                        "shape": shape_key
                    })
                
                #WAAPI
                args = {
                    "object": obj_id,
                    "curveType": attenuation_map[self.att_var_string.get()],
                    "use": "Custom",
                    "points": points_payload
                }
                
                self.client.call("ak.wwise.core.object.setAttenuationCurve", args)
        
        except Exception as e:
            traceback.print_exc()
            print(str(e))

            
    def get_attenuation(self):
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
            for point in self.points[:]:
                point.destroy()
            self.points.clear()
            get_args = {"object": first_object_id, "curveType": attenuation_map[self.att_var_string.get()]}
            get_att = self.client.call("ak.wwise.core.object.getAttenuationCurve", get_args)
            points = get_att.get('points', [])
            if points:
                max_x_value = max(p['x'] for p in points)
                self.current_max_x = max_x_value
                for p in points:
                    scaled_x = (p['x'] / max_x_value) * 100
                    new_point = self._create_point(scaled_x, p['y'])
                    new_point.att_curve_string.set(shape_display_map[p.get('shape', 'Linear')])
                self.graph_display_status = 'points'
                self.show_controls()
            else:
                self.graph_display_status = 'no_points'
                self.hide_controls()
            self.update_graph()
        except Exception as e:
            traceback.print_exc()
            print(str(e))
            
    def close_connection(self):
        try:
            self.client.disconnect()
        except Exception as e:
            print("Error while closing the connection:", e)

# main window
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

if __name__ == "__main__":
    app.mainloop()
