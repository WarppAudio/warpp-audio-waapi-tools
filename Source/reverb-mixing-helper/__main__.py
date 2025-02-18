
import traceback
import customtkinter

from customtkinter import (
    CTk,
    CTkFrame,
    CTkButton,
    CTkCheckBox,
    CTkLabel,
    CTkEntry,
    CTkScrollableFrame
)

from waapi import WaapiClient

ver = "v1.0.0"

DARK_BG = "#2E2E2E"  
GREY_BG = "#212120"

def truncate_text(text, max_chars=40):
    return text if len(text) <= max_chars else text[:max_chars - 3] + "..."

# Class representing sounds
class Sound:
    def __init__(self, parent, app, index, on_delete=lambda idx: None):
        self.app = app          # Reference to main app
        self.index = index
        self.on_delete = on_delete
        self.is_playing = False
        self.transport_id = None
        self.current_object_id = None

        # Frame for sounds
        self.frame = CTkFrame(parent, fg_color=DARK_BG)
        self.frame.pack(fill="x", pady=5)

        # Columns configuration
        self.frame.columnconfigure(0, weight=0)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=0)
        self.frame.columnconfigure(3, weight=0)
        self.frame.columnconfigure(4, weight=0)
        self.frame.columnconfigure(5, weight=0)

        self.sound_id_entry = CTkEntry(
            self.frame,
            width=100,
            placeholder_text="Sound ID"
        )
        self.sound_id_entry.grid(row=0, column=0, padx=5)
        self.sound_id_entry.bind("<KeyRelease>", lambda e: self.get_object_name())

        self.sound_name_label = CTkLabel(
            self.frame,
            text="Name"
        )
        self.sound_name_label.grid(row=0, column=1, padx=5, sticky="w")

        # Text icon placeholder
        self.icon_label = CTkLabel(
            self.frame,
            text="",
            width=20,
            fg_color=DARK_BG
        )
        self.icon_label.grid(row=0, column=2, padx=5)

        self.loop_check = CTkCheckBox(
            self.frame,
            text="Loop",
            fg_color=DARK_BG
        )
        self.loop_check.grid(row=0, column=3, padx=5)

        self.play_stop_button = CTkButton(
            self.frame,
            text="Play",
            width=45,
            fg_color=("#337733", "#337733"),
            hover_color=("#449944", "#449944"),
            command=self.toggle_play_stop
        )
        self.play_stop_button.grid(row=0, column=4, padx=5)

        self.delete_button = CTkButton(
            self.frame,
            text="Delete",
            fg_color=("#803333", "#803333"),
            hover_color=("#993333", "#993333"),
            width=50,
            command=lambda: self.on_delete(self.index)
        )
        self.delete_button.grid(row=0, column=5, padx=5)

    def get_object_name(self):
        try:
            object_id = self.sound_id_entry.get().strip()
            if not object_id:
                self.sound_name_label.configure(text="")
                return

            # If user entered a new ID - Reset Transport
            
            if self.current_object_id != object_id:
                self.current_object_id = object_id
                self.transport_id = None

            if not self.app.client:
                self.sound_name_label.configure(text="No WAAPI client")
                return

            # GUID validation
            if len(object_id) == 38 and object_id.startswith('{') and object_id.endswith('}'):
                id_value = object_id
            else:
                self.sound_name_label.configure(text="Invalid ID format")
                return

            try:
                result = self.app.client.call(
                    "ak.wwise.core.object.get",
                    {"from": {"id": [id_value]}},
                    {"return": ["id", "type", "name"]}
                )
                if result and "return" in result and len(result["return"]) > 0:
                    name = result["return"][0].get("name")
                    self.sound_name_label.configure(text=name)
                else:
                    self.sound_name_label.configure(text="Object not found")
            except Exception as api_error:
                print(f"WAAPI error: {api_error}")
                self.sound_name_label.configure(text="Invalid ID")
        except Exception as e:
            traceback.print_exc()
            print(f"Error in get_object_name: {e}")
            self.sound_name_label.configure(text="Error")

    def create_transport(self, object_id):
        if not self.app.client:
            return
        try:
            response = self.app.client.call("ak.wwise.core.transport.create", {"object": object_id})
            if response:
                self.transport_id = response.get("transport")
        except Exception as e:
            traceback.print_exc()
            print(f"Error creating transport: {e}")

    def schedule_check_state(self, delay_ms=400):
        self.icon_label.after(delay_ms, self.check_state_and_loop)

    def check_state_and_loop(self):
        # If the sound is not supposed to be playing, exit the function
        if not self.is_playing:
            return

        if not self.transport_id or not self.app.client:
            return
        try:
            state_args = {"transport": self.transport_id}
            state_response = self.app.client.call("ak.wwise.core.transport.getState", state_args)
            if not state_response:
                print("Transport getState returned None.")
                return

            current_state = state_response.get("state", "").lower().strip()
            print(f"[Sound {self.index}] Transport state: {repr(current_state)}")

            if current_state in ["stopped", "finished", "ended"]:
                # If loop is enabled and sound should continue playing, delay before replaying
                if self.loop_check.get() == 1 and self.is_playing:
                    try:
                        delay_str = self.app.sequence_delay_entry.get().strip()
                        delay = int(delay_str) if delay_str else 0
                    except Exception as ex:
                        delay = 0
                    # Delay the playback by the specified delay
                    self.app.after(delay, lambda: self.app.client.call("ak.wwise.core.transport.executeAction",
                                                                    {"transport": self.transport_id, "action": "play"}))
                    # Schedule the next state check with the same delay
                    self.schedule_check_state(delay_ms=delay)
                    return
                else:
                    self.is_playing = False
                    self.play_stop_button.configure(
                        text="Play",
                        fg_color=("#337733", "#337733"),
                        hover_color=("#449944", "#449944")
                    )
                    self.sound_id_entry.configure(state="normal")
                    self.loop_check.configure(state="normal")
                    self.delete_button.configure(state="normal")
                    self.clear_icon()

                    if self.app.var_sequence.get() and not self.app.sequence_stopped:
                        next_index = (self.index + 1) % len(self.app.sound_list)
                        try:
                            delay_str = self.app.sequence_delay_entry.get().strip()
                            delay = int(delay_str) if delay_str else 0
                        except Exception as ex:
                            delay = 0
                        self.app.after(delay, lambda: self.app.sound_list[next_index].toggle_play_stop(sequence_playing=True))
                    return

            if self.is_playing:
                self.schedule_check_state()
        except Exception as e:
            traceback.print_exc()
            print(f"Error in check_state_and_loop: {e}")



    def toggle_play_stop(self, sequence_playing=False):
        object_id = self.sound_id_entry.get().strip()
        if not object_id:
            print("No sound ID provided.")
            return

        if not self.app.client:
            print("WAAPI client not connected.")
            return

        if not self.transport_id:
            self.create_transport(object_id)
            if not self.transport_id:
                print("No transport ID created.")
                return

        try:
            if not self.is_playing:
                if sequence_playing and self.app.sequence_stopped:
                    return

                self.app.sequence_stopped = False
                self.is_playing = True
                self.play_stop_button.configure(
                    text="Stop",
                    fg_color=("#883333", "#883333"),
                    hover_color=("#993333", "#993333")
                )
                self.sound_id_entry.configure(state="disabled")
                self.loop_check.configure(state="disabled")
                self.delete_button.configure(state="disabled")

                
                # Use text character "▶" as "playin sound icon"
                self.icon_label.configure(text="▶")

                play_args = {"transport": self.transport_id, "action": "play"}
                self.app.client.call("ak.wwise.core.transport.executeAction", play_args)

                self.schedule_check_state()
            else:
                stop_args = {"transport": self.transport_id, "action": "stop"}
                self.app.client.call("ak.wwise.core.transport.executeAction", stop_args)
                self.is_playing = False

                self.play_stop_button.configure(
                    text="Play",
                    fg_color=("#337733", "#337733"),
                    hover_color=("#449944", "#449944")
                )
                self.sound_id_entry.configure(state="normal")
                self.loop_check.configure(state="normal")
                self.delete_button.configure(state="normal")
                self.clear_icon()
        except Exception as e:
            traceback.print_exc()
            print(f"Error in toggle_play_stop: {e}")
            
    def clear_icon(self):
     
        #Remove "icon" 
        self.icon_label.configure(text="")
        self.icon_label.update_idletasks()

# Main App
class MainApp(CTk):
    def __init__(self):
        super().__init__()

        self.title("Reverb Mixing Helper")
        self.geometry("800x400")
        self.attributes('-topmost', True)

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("dark-blue")

        try:
            self.client = WaapiClient()
            project_info = self.client.call("ak.wwise.core.getProjectInfo")
            self.project_name = project_info.get("name", "Unknown")
        except Exception as e:
            print(f"Could not connect to Wwise: {e}")
            self.client = None
            self.project_name = "Not Connected"

        self.sound_list = []
        self.subscription_id = None
        self.sequence_stopped = False

        self.configure(fg_color=DARK_BG)

        self.main_frame = CTkFrame(self, fg_color=GREY_BG)
        self.main_frame.pack(fill="both", expand=True)

        self.control_frame = CTkFrame(self.main_frame, fg_color=DARK_BG)
        self.control_frame.pack(fill="x", padx=5, pady=5)

        # AUX Tracking 
        self.aux_button_icon_frame = CTkFrame(self.control_frame, fg_color=DARK_BG)
        self.aux_button_icon_frame.pack(side="left", padx=(0, 20))

        self.toggle_aux_button = CTkButton(
            self.aux_button_icon_frame,
            text="Start AUX Tracking",
            width=150,
            fg_color=("#337733", "#337733"),
            hover_color=("#449944", "#449944"),
            command=self.toggle_aux_function
        )
        self.toggle_aux_button.pack(side="left", padx=(0,5))

        self.aux_icon_label = CTkLabel(
            self.aux_button_icon_frame,
            text="",  # Initially an empty label for animation
            width=24,
            fg_color=DARK_BG
        )
        self.aux_icon_label.pack(side="left", padx=(0,5))

        self.selected_aux_label = CTkLabel(
            self.aux_button_icon_frame,
            text="AUX: Selected None",
            fg_color=DARK_BG, width=200, anchor="w", font=("TkDefaultFont", 10)
        )
        self.selected_aux_label.pack(side="left")

        # Initialization of the spinner for AUX animation (ASCII characters)
        self.aux_spinner_chars = ["|", "/", "-", "\\"]
        self.aux_spinner_index = 0
        self.aux_rotating = False
        self.aux_icon_after_id = None

        # Sequence controls and buttons for adding/stopping
        self.sequence_delay_entry = CTkEntry(self.control_frame, width=70, placeholder_text="Delay(ms)")
        self.sequence_check = CTkCheckBox(self.control_frame, text="Sequence", fg_color=DARK_BG)
        self.var_sequence = customtkinter.BooleanVar()
        self.sequence_check.configure(variable=self.var_sequence)
        self.sequence_check.pack(side="right", padx=(5,5))
        self.sequence_delay_entry.pack(side="right", padx=(5,5))
        self.sequence_stop_button = CTkButton(
            self.control_frame,
            text="Stop All",
            fg_color=("#803333", "#803333"),
            hover_color=("#993333", "#993333"),
            width=50,
            command=self.stop_sequence
        )
        self.sequence_stop_button.pack(side="right", padx=(5,0))
        self.add_sound_button = CTkButton(
            self.control_frame,
            text="Add",
            width=50,
            fg_color=("#333333", "#333333"),
            hover_color=("#444444", "#444444"),
            command=self.add_sound
        )
        self.add_sound_button.pack(side="right", padx=(10,0))

        #Scrollable Frame for sounds
        self.sound_frame = CTkScrollableFrame(self.main_frame, fg_color=DARK_BG)
        self.sound_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Footer / project label
        self.project_label_frame = CTkFrame(self.main_frame, fg_color=DARK_BG)
        self.project_label_frame.pack(fill="x", padx=5, pady=(0,5))
        self.project_label = CTkLabel(
            self.project_label_frame,
            text="Project: " + (self.project_name or "Unknown"),
            fg_color=DARK_BG
        )
        self.project_label.pack(side="left")
        
        self.verion_label = CTkLabel(
            self.project_label_frame,
            text=ver,
            fg_color=DARK_BG
        )
        self.verion_label.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        self.stop_sequence()
        if self.client:
            self.client.disconnect()
        self.destroy()
        
    def assign_aux_send(self, **kwargs):
        try:
            if not kwargs.get('objects'):
                print("No objects in kwargs, ignoring.")
                return

            selected_obj = kwargs['objects'][0]
            id_aux = selected_obj.get('id')
            if not id_aux:
                print("No 'id' in the object, ignoring.")
                return

            if not self.client:
                print("No WAAPI client, cannot get aux info.")
                return

            aux_bus_info = self.client.call("ak.wwise.core.object.get", {
                "from": {"id": [id_aux]},
            }, {"return": ["name"]})
            if not aux_bus_info or not aux_bus_info.get("return"):
                print("Could not fetch AuxBus info.")
                return

            aux_bus_name = aux_bus_info["return"][0].get("name", "Unknown")
            selected_object_type = selected_obj.get('type', None)

            if selected_object_type == 'AuxBus':
                truncated_name = truncate_text(aux_bus_name, max_chars=42)
                self.selected_aux_label.configure(text=f"AUX: {truncated_name}")
            else:
                self.selected_aux_label.configure(text="AUX: Selected None")

            if selected_object_type == 'AuxBus':
                for sound in self.sound_list:
                    sound_id = sound.sound_id_entry.get().strip()
                    if sound_id:
                        set_args = {
                            "object": sound_id,
                            "reference": "UserAuxSend0",
                            "value": id_aux
                        }
                        try:
                            self.client.call("ak.wwise.core.object.setReference", set_args)
                            print(f"Updated Aux Send for sound {sound_id} to {id_aux}")
                            #overide parrent user aux sends
                            override_args = {
                            "object": sound_id,
                            "property": "OverrideUserAuxSends", 
                            "value": True
                            }
                            self.client.call("ak.wwise.core.object.setProperty", override_args)
                            
                        except Exception as aux_e:
                            print(f"Failed to set Aux Send for sound {sound_id}: {aux_e}")
        except Exception as e:
            traceback.print_exc()
            print(f"Error in assign_aux_send: {str(e)}")

    def start_aux_icon_animation(self):
        self.aux_rotating = True
        self.aux_spinner_index = 0
        self.animate_aux_icon()

    def animate_aux_icon(self):
        if not self.aux_rotating:
            return
        try:
            # Update the spinner label with the next character
            spinner_char = self.aux_spinner_chars[self.aux_spinner_index]
            self.aux_icon_label.configure(text=spinner_char)
            self.aux_spinner_index = (self.aux_spinner_index + 1) % len(self.aux_spinner_chars)
            self.aux_icon_after_id = self.after(200, self.animate_aux_icon)
        except Exception as e:
            print(f"Error animating AUX icon: {e}")

    def stop_aux_icon_animation(self):
        self.aux_rotating = False
        if self.aux_icon_after_id:
            self.after_cancel(self.aux_icon_after_id)
            self.aux_icon_after_id = None
        self.aux_icon_label.configure(text="")
        
    def toggle_aux_function(self):
        if self.subscription_id is None:
            if not self.client:
                print("Cannot start AUX tracking, no WAAPI client.")
                return
            self.toggle_aux_button.configure(
                text="Stop AUX Tracking",
                fg_color=("#883333", "#883333"),
                hover_color=("#993333", "#993333")
            )
            self.aux_icon_label.configure(text="")
            self.start_aux_icon_animation()
            try:
                self.subscription_id = self.client.subscribe(
                    "ak.wwise.ui.selectionChanged",
                    self.assign_aux_send,
                    {"return": ["type", "id"]}
                )
                print("Subscription started.")
            except Exception as e:
                print(f"Subscription failed: {e}")
        else:
            self.toggle_aux_button.configure(
                text="Start AUX Tracking",
                fg_color=("#337733", "#337733"),
                hover_color=("#449944", "#449944")
            )
            self.stop_aux_icon_animation()
            self.aux_icon_label.configure(text="")
            try:
                if self.client and self.subscription_id is not None:
                    self.client.unsubscribe(self.subscription_id)
                    self.subscription_id = None
                print("Unsubscription successful.")
            except Exception as e:
                print(f"Unsubscription failed: {e}")

    def add_sound(self):
        index = len(self.sound_list)
        new_sound = Sound(self.sound_frame, self, index, on_delete=self.delete_sound)
        self.sound_list.append(new_sound)

    def delete_sound(self, index):
        sound_obj = self.sound_list[index]
        sound_obj.frame.destroy()
        self.sound_list.pop(index)
        for i, snd in enumerate(self.sound_list):
            snd.index = i

    def stop_sequence(self):
        self.sequence_stopped = True
        for s in self.sound_list:
            if s.is_playing:
                s.toggle_play_stop()
            else:
                s.clear_icon()

def main():
    app = MainApp()
    app.mainloop()
    if app.client:
        app.client.disconnect()

if __name__ == "__main__":
    main()
