import os
import sys
import re
import json
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
from waapi import WaapiClient



client = None

def open_waapi_connection():
    global client
    if client is None:
        client = WaapiClient()
    return client

def close_waapi_connection():
    global client
    if client is not None and client.is_connected():
        client.disconnect()
        client = None


created_events = []
created_event_seek_names = []
created_items_dict = {}
settings_valid = True

class SettingsManager:
    def __init__(self):
        

        def get_resource_path(filename):
            # Running  „frozen” (.exe)
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                # Running as  .py
                base_path = os.path.dirname(os.path.realpath(__file__))

            return os.path.join(base_path, filename)

        self.path = get_resource_path('settings.json')


        self.settings = {
            'NAMING_CONVENTION': [],
            'WORDS_REMOVE': [],
            'NAMING_FOR_LOOPS': '',
            'SOUND_NAMING_FOR_LOOPS': [],
            'WORDS_NOT_CAPITALIZE': [],
            'PLAY_NAMING_CONVENTION': '',
            'STOP_NAMING_CONVENTION': '',
            'STOP_EVENT_FOR_LOOPS': False,
            'LETTER_CASE_EVENT_NAME': None,
            'PLAY_LOOP_FADE_TIME': 0.0,
            'STOP_LOOP_FADE_TIME': 0.0,
            'SEEK_ACTION_FOR_LOOPS': False,
            'SEEK_Percent': 0.0,
            'SEEK_RANDOM_MIN': 0.0,
            'SEEK_RANDOM_MAX': 0.0
        }
        print(f"Loading settings from: {self.path}")
        self.load()


    def load(self):
        try:
          
            if not os.path.exists(self.path):
                print("Creating new settings file")
                self.save()
                return

            with open(self.path, 'r') as file:
                loaded_settings = json.load(file)
                
                for key in self.settings.keys():
                    if key in loaded_settings:
                        self.settings[key] = loaded_settings[key]
                print("Settings loaded successfully")
                
        except FileNotFoundError:
            print("JSON NOT FOUND")
            messagebox.showerror("JSON Not Found", f"Settings file not found at: {self.path}")
        except json.JSONDecodeError:
            print("JSON FORMAT ERROR")
            messagebox.showerror("JSON Format Error", "The settings file is corrupted or has incorrect format.")
        except Exception as e:
            print(f"Unexpected error loading settings: {e}")
            messagebox.showerror("Load Error", f"An unexpected error occurred while loading settings: {e}")

    def save(self):
        try:
    
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            
            with open(self.path, 'w') as file:
                json.dump(self.settings, file, indent=4)
                print("Settings saved successfully")
        except Exception as e:
            print(f"Error saving settings: {e}")
            messagebox.showerror("Save Error", f"An error occurred while saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

# initialize  SettingsManager
settings_manager = SettingsManager()


def format_event_name(name: str, prefix: str, settings_manager, parent_workunit: str = None) -> str:
    """
    Format the event name by applying a prefix, handling wildcards, and adjusting letter casing.
    Wildcard $parent in prefix will be replaced by parent_workunit if provided.
    """
    # Handle $parent wildcard in the prefix
    if parent_workunit and '$parent' in prefix:
        prefix = prefix.replace('$parent', parent_workunit)

    # Normalize separators
    prefix = re.sub(r'[\s,]+', '_', prefix).strip('_')
    prefix = re.sub(r'__+', '_', prefix)

    # Retrieve settings
    words_not_capital = settings_manager.get('WORDS_NOT_CAPITALIZE', [])
    letter_case_event_name = settings_manager.get('LETTER_CASE_EVENT_NAME', None)
    loop_naming = settings_manager.get('NAMING_FOR_LOOPS', '')

    # Prepare patterns for words to skip capitalization
    direct_words = []
    regex_words = []
    for item in words_not_capital:
        item_strip = item.strip()
        if '#' in item_strip:

            pattern = '^' + item_strip.replace('#', r'\d+') + '$'
            try:
                regex_words.append(re.compile(pattern))
            except re.error:
                continue
        else:
            direct_words.append(item_strip)

    # Replace spaces and dashes
    base_name = name.replace(' ', '_').replace('-', '_')
    base_name = re.sub(r'__+', '_', base_name)

    # Split base name into words
    words = base_name.strip('_').split('_')
    formatted_words = []

    for word in words:
        skip_capitalization = False

        # Check if word matches direct or regex skip lists
        if word in direct_words or word == loop_naming:
            skip_capitalization = True
        else:
            for rgx in regex_words:
                if rgx.match(word):
                    skip_capitalization = True
                    break

        # Apply casing or keep as-is
        if skip_capitalization:
            formatted_words.append(word)
        else:
            if letter_case_event_name == 'upper':
                formatted_words.append(word.capitalize())
            elif letter_case_event_name == 'lower':
                formatted_words.append(word.lower())
            else:
                formatted_words.append(word)

    # Join formatted words with underscores
    formatted_base = '_'.join(formatted_words)

    # Ensure prefix ends with underscore if not empty
    if prefix and not prefix.endswith('_'):
        prefix += '_'

    # Combine prefix and formatted base, remove any trailing underscores
    full_name = f"{prefix}{formatted_base}".strip('_')
    return full_name






def event_exists(event_name, client):
    """
    Returns True if event already exists in the Wwise project,
    using an already-open WaapiClient.
    """
    options = {"return": ["id", "name"]}
    query = {
        "waql": f'$ from type Event where name = "{event_name}"'
    }
    result = client.call("ak.wwise.core.object.get", query, options=options)
    found_objects = result.get("return", [])
    return len(found_objects) > 0

def check_if_is_loop_sound(sound_name: str, tokens: list[str]) -> bool:
    """
    Checks if 'sound_name' contains any of the given 'tokens' in a case-sensitive manner.
    A token must be preceded by start-of-string, underscore, or dash,
    and followed by underscore, dash, or end-of-string.
    Example: for token = "loop", we only match:
    _loop, loop_, _loop_, ^loop, loop$ or dash-based variants: -loop, loop-, etc.
    """
    for token in tokens:
        # Escape user-defined token in case it contains special regex characters
        token_escaped = re.escape(token.strip())

        pattern = re.compile(r'(?:^|_|-)' + token_escaped + r'(?:_|-|$)')

        # If the pattern matches anywhere in the sound_name, return True immediately
        if pattern.search(sound_name):
            return True
    return False

def create_event_play(name: str,
                      target,
                      client,
                      is_loop: bool = False,
                      parent_workunit: str = None) -> dict:
    """
    Create a Play event object. If $parent wildcard was used,
    parent_workunit is already applied in the prefix.
    """
    # Retrieve user-defined naming prefix for Play events
    play_naming = settings_manager.get("PLAY_NAMING_CONVENTION", "")
    # Format final event name with optional wildcard replacement
    event_name = format_event_name(name, play_naming, settings_manager, parent_workunit)
    # Fade time for looped sounds
    play_loop_fade_time = settings_manager.get("PLAY_LOOP_FADE_TIME", 0.0)

    # Skip creation if event already exists
    if event_exists(event_name, client):
        print(f"[SKIP] Event '{event_name}' already exists in project, skipping.")
        return None

    # Build the Play action
    action = {
        "type": "Action",
        "@ActionType": 1,
        "name": "Start",
        "@Target": target
    }
    # Apply fade time on loops
    if is_loop:
        action["@FadeTime"] = play_loop_fade_time

    # Construct and return the event payload
    event = {
        "type": "Event",
        "name": event_name,
        "children": [action]
    }
    return event






def create_event_stop(name, target, client, parent_workunit=None):
    
    """
    Create a Stop event object. Supports $parent wildcard in prefix.
    """

    stop_naming = settings_manager.get("STOP_NAMING_CONVENTION", "")
    event_name = format_event_name(name, stop_naming, settings_manager, parent_workunit)
    stop_loop_fade_time = settings_manager.get("STOP_LOOP_FADE_TIME", 0.0)

    # Skip creation if event already exists
    if event_exists(event_name, client):
        print(f"[SKIP] Event '{event_name}' already exists in project, skipping.")
        return None

    # Build the Stop action
    action = {
        "type": "Action",
        "@ActionType": 2,
        "@FadeTime": stop_loop_fade_time,
        "name": "",
        "@Target": target
    }

    # Construct and return the event payload
    event = {
        "type": "Event",
        "name": event_name,
        "children": [action]
    }
    return event



def create_event_seek(name, target, client, parent_workunit=None):
    play_naming = settings_manager.get("PLAY_NAMING_CONVENTION", "")
    event_name = format_event_name(name, play_naming, settings_manager, parent_workunit)
    play_loop_fade_time = settings_manager.get("PLAY_LOOP_FADE_TIME", 0.0)
    seek_percent = settings_manager.get("SEEK_Percent", 0.0)

    if event_exists(event_name, client):
        print(f"[SKIP] Event '{event_name}' already exists in project, skipping.")
        return None

    event = {
        "type": "Event",
        "name": event_name,
        "children": [
            {
                "type": "Action",
                "@ActionType": 1,
                "@FadeTime": play_loop_fade_time,
                "name": "Start",
                "@Target": target
            },
            {
                "type": "Action",
                "@ActionType": 36,
                "@SeekPercent": seek_percent,
                "@Inclusion": True,
                "name": "Seek",
                "@Target": target
            },
        ]
    }
    created_event_seek_names.append(event_name)
    return event




def create_new_workunit(parent_path, new_workunit_name):
    global client
    create_args = {
        "parent": parent_path,
        "type": "WorkUnit",
        "name": new_workunit_name
    }
    response = client.call("ak.wwise.core.object.create", create_args)
    created_id = response["id"]

    # Text to show in the created events listbox
    fullpath = str(create_args["parent"])
    parts = fullpath.strip("\\").split("\\")
    last_part = parts[-1]
    display_text = str(last_part + "\\" + create_args['name'] + " [W]")

    # Update created events in listbox, with ID
    update_events_listbox(display_text, created_id)


def create_new_folder(parent_path, new_folder_name):
    global client
    create_args = {
        "parent": parent_path,
        "type": "Folder",
        "name": new_folder_name
    }
    response = client.call("ak.wwise.core.object.create", create_args)
    created_id = response["id"]

    fullpath = str(create_args["parent"])
    parts = fullpath.strip("\\").split("\\")
    last_part = parts[-1]
    display_text = str(last_part + "\\" + create_args['name'] + " [F]")

    update_events_listbox(display_text, created_id)

def create_play_or_seek_event(name: str,
                               target,
                               is_loop: bool,
                               client,
                               parent_workunit: str = None) -> dict:

    # Check user setting for generating Seek actions on loops
    seek_for_loops = settings_manager.get('SEEK_ACTION_FOR_LOOPS', False)
    if is_loop and seek_for_loops:
        # Note: create_event_seek signature may need to accept parent_workunit
        return create_event_seek(name, target, client, parent_workunit)
    else:
        return create_event_play(name, target, client, is_loop, parent_workunit)





def create_events_for_selection(wwu_path, new_wwu):
    global client
    try:
        options = {"return": ["id", "isPlayable", "name", "originalWavFilePath", "ChannelConfigOverride"]}
        selected = client.call("ak.wwise.ui.getSelectedObjects", {}, options=options)["objects"]

        set_args = {"objects": [], "onNameConflict": "merge"}
        created = []
        seeks = []
        incorrect = []

        words_remove = settings_manager.get("WORDS_REMOVE", [])
        loop_tokens = settings_manager.get("SOUND_NAMING_FOR_LOOPS", [])
        naming_conv = settings_manager.get("NAMING_CONVENTION", [])
        loop_suffix = settings_manager.get("NAMING_FOR_LOOPS", "")
        stop_loops = settings_manager.get("STOP_EVENT_FOR_LOOPS", False)
        seek_loops = settings_manager.get("SEEK_ACTION_FOR_LOOPS", False)
        seek_min = settings_manager.get("SEEK_RANDOM_MIN", 0.0)
        seek_max = settings_manager.get("SEEK_RANDOM_MAX", 0.0)

        parent = new_wwu or wwu_path.strip("\\").split("\\")[-1]

        for obj in selected:
            if not obj.get("isPlayable"):
                continue

            name = obj["name"]
            for w in words_remove:
                name = name.replace(w, "")
            name = re.sub(r"_+", "_", name).strip("_")

            is_loop = check_if_is_loop_sound(name, loop_tokens)
            if is_loop:
                for t in loop_tokens:
                    name = name.replace(t, "")
                name = re.sub(r"_+", "_", name).strip("_")
                name = name.replace(loop_suffix, "").strip("_")
                name = f"{name}_{loop_suffix}".strip("_")

            children = []
            evt = create_play_or_seek_event(name, obj["id"], is_loop, client, parent)
            if evt:
                children.append(evt)
                created.append(evt["name"])
                if is_loop and seek_loops:
                    seeks.append(evt["name"])

            if is_loop and stop_loops:
                stop_evt = create_event_stop(name, obj["id"], client, parent)
                if stop_evt:
                    children.append(stop_evt)
                    created.append(stop_evt["name"])

            target = f"{wwu_path}\\{new_wwu}" if new_wwu else wwu_path
            set_args["objects"].append({"object": target, "children": children})

            src_q = {"waql": f'$ "{obj["id"]}" select this, descendants where type = "AudioFileSource"'}
            for src in client.call("ak.wwise.core.object.get", src_q, options=options)["return"]:
                if not any(p in src["name"] for p in naming_conv):
                    incorrect.append(src["name"])

        client.call("ak.wwise.core.object.set", set_args)

        for seek_name in seeks:
            q = {"waql": f'$ from type Action where actionType = 36 and parent.name = "{seek_name}"'}
            acts = client.call("ak.wwise.core.object.get", q, options={"return": ["id"]})["return"]
            for a in acts:
                client.call("ak.wwise.core.object.setRandomizer", {
                    "object": str(a["id"]),
                    "enabled": True,
                    "property": "SeekPercent",
                    "min": seek_min,
                    "max": seek_max,
                })

        for name in created:
            q = {"waql": f'$ from type Event where name = "{name}"'}
            res = client.call("ak.wwise.core.object.get", q, options={"return": ["id"]})
            if res.get("return"):
                update_events_listbox(f"{name} [E]", res["return"][0]["id"])

        if incorrect and naming_conv:
            messagebox.showerror("Naming Convention Error", "\n".join(incorrect))

    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Error", str(e))



def get_workunit_path():
    global client
    # Define the options for the query
    options = {"return": ["path", "id", "isPlayable", "originalWavFilePath", "parent.id", "ChannelConfigOverride", "name", "type"]}

    wwu_query = {
        'waql': '$ from type workunit where category = "Events"',
    }
    wwu_result = client.call("ak.wwise.core.object.get", wwu_query, options=options)

    folder_query = {
        'waql': '$ from type folder where category = "Events"',
    }
    folder_result = client.call("ak.wwise.core.object.get", folder_query, options=options)

    combined_results = wwu_result.get('return', []) + folder_result.get('return', [])


    paths = [item['path'] for item in combined_results]
    return paths


def get_workunit_names():
    global client
    options_wwu = {
        "return": [
            "path",
            "id",
            "isPlayable",
            "originalWavFilePath",
            "parent.id",
            "ChannelConfigOverride",
            "name",
            "type"
        ]
    }
    wwuargs = {
        'waql': '$ from type workunit where category = "Events"',
    }

    result = client.call("ak.wwise.core.object.get", wwuargs, options=options_wwu)['return']
    names = list(map(lambda x: x['name'], result))
    paths = list(map(lambda x: x['path'], result))
    return names


def get_folder_names():
    global client
    options_wwu = {
        "return": [
            "path",
            "id",
            "isPlayable",
            "originalWavFilePath",
            "parent.id",
            "ChannelConfigOverride",
            "name",
            "type"
        ]
    }
    wwuargs = {
        'waql': '$ from type folder where category = "Events"',
    }

    result = client.call("ak.wwise.core.object.get", wwuargs, options=options_wwu)['return']
    names = list(map(lambda x: x['name'], result))
    paths = list(map(lambda x: x['path'], result))
    return names


def get_all_workunits():
    """
    Returns list ( (name, path), ... ) of every work unit in the 'Events' category.
    """
    global client
    options = {"return": ["id", "name", "path", "type"]}
    wwu_query = {
        'waql': '$ from type WorkUnit where category = "Events"',
    }
    result = client.call("ak.wwise.core.object.get", wwu_query, options=options)
    all_wwu = []
    for item in result.get("return", []):
        all_wwu.append((item['name'], item['path']))
    return all_wwu


def get_all_folders():
    """
    Returns list ( (name, path), ... ) of every folder in the 'Events' category.
    """
    global client
    options = {"return": ["id", "name", "path", "type"]}
    folder_query = {
        'waql': '$ from type Folder where category = "Events"',
    }
    result = client.call("ak.wwise.core.object.get", folder_query, options=options)
    all_folders = []
    for item in result.get("return", []):
        all_folders.append((item['name'], item['path']))
    return all_folders


def get_parent_path(full_path):
    """
    Returns the parent path (without the last component).
    Example:
      "\\Events\\Music\\NewWWU" -> "\\Events\\Music"
      "\\Events" -> "" (no parent)
    """
    parts = full_path.strip("\\").split("\\")
    if len(parts) <= 1:
        return ""
    parent_parts = parts[:-1]
    return "\\".join([""] + parent_parts)


def can_create_workunit(new_name, parent_path):
    """
    Checks if a new WorkUnit named 'new_name' can be created in 'parent_path'.
    Returns True/False.

    Conditions:
    1) No other WorkUnit in the entire project can have the same name (workunits must be globally unique).
    2) No folder with the same name can exist in the same parent_path.
    """
    all_wwu = get_all_workunits()
    all_fld = get_all_folders()


    for wwu_name, wwu_path in all_wwu:
        if wwu_name.lower() == new_name.lower():
            return False  


    for fld_name, fld_path in all_fld:
        if fld_name.lower() == new_name.lower():
            if get_parent_path(fld_path) == parent_path:
                return False

    return True


def can_create_folder(new_name, parent_path):
    """
    Checks if it's possible to create a new Folder (virtual folder) with the name 'new_name'
    in the parent 'parent_path'.
    Returns True/False.

    Conditions:
    - There cannot be another Folder with the same name in the same parent_path.
    - There cannot be a WorkUnit with the same name in the same parent_path.
    """
    all_fld = get_all_folders()
    for fld_name, fld_path in all_fld:
        if fld_name.lower() == new_name.lower():
            if get_parent_path(fld_path) == parent_path:
                return False

    all_wwu = get_all_workunits()
    for wwu_name, wwu_path in all_wwu:
        if wwu_name.lower() == new_name.lower():
            if get_parent_path(wwu_path) == parent_path:
                return False

    return True


def handle_create_events():
    if not settings_valid:
        messagebox.showerror("Error", "Cannot create events due to invalid settings. Please fix the fields marked in red.")
        return

    workunit_path = paths_var_string.get()
    new_parent_name = entry_str_new_parent.get().strip()

    if show_entry_new_folder_var.get() == 1 and new_parent_name:
        if not can_create_folder(new_parent_name, workunit_path):
            messagebox.showinfo(
                "Virtual Folder Name Conflict",
                f"Object with name: {new_parent_name}, already exists in this location"
            )
            return  # silent return -> nothing is created, no events
        else:
            create_new_folder(workunit_path, new_parent_name)

    if show_entry_new_wwu_var.get() == 1 and new_parent_name:
        if not can_create_workunit(new_parent_name, workunit_path):
            messagebox.showinfo("Work Unit Name Conflict", f"Work Unit: {new_parent_name}, already exists")
            return  # silent return
        else:
            create_new_workunit(workunit_path, new_parent_name)

    try:
        refresh_workunit_list()
        create_events_for_selection(workunit_path, new_parent_name)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")



# GUI FUNCTIONS AND CLASSES


def update_stop_event_for_loops(*args):
    stop_event_for_loops = stop_event_var.get()
    settings_manager.set('STOP_EVENT_FOR_LOOPS', stop_event_for_loops)


def update_seek_event_for_loops(*args):
    seek_event_for_loops = seek_event_var.get()
    settings_manager.set('SEEK_ACTION_FOR_LOOPS', seek_event_for_loops)




def update_letter_case():
    if capitalize_var.get():
        letter_case_event_name = 'upper'
    elif lowercase_var.get():
        letter_case_event_name = 'lower'
    else:
        letter_case_event_name = None
    settings_manager.set('LETTER_CASE_EVENT_NAME', letter_case_event_name)


def update_words_not_capital(*args):
    words_not_capital_input = words_not_capital_Var.get()
    # Split on commas and strip spaces
    words_not_capital = [word.strip() for word in re.split(r',\s*', words_not_capital_input) if word.strip()]
    settings_manager.set('WORDS_NOT_CAPITALIZE', words_not_capital)
    print("Updated words_not_capital:", words_not_capital)




def update_naming_convention(*args):
    naming_convention_input = naming_convention_var.get()
    naming_convention = [word.strip() for word in naming_convention_input.split(', ') if word.strip()]
    settings_manager.set('NAMING_CONVENTION', naming_convention)




def update_words_remove(*args):
    words_remove_input = words_remove_var.get()
    words_remove = [word.strip() for word in words_remove_input.split(', ') if word.strip()]
    settings_manager.set('WORDS_REMOVE', words_remove)



def update_loop_sound_naming(*args):
    try:

        value = loop_sound_naming_var.get()
        sound_naming = [word.strip() for word in value.split(',') if word.strip()]
        settings_manager.set('SOUND_NAMING_FOR_LOOPS', sound_naming)
        
        print(f"Updated SOUND_NAMING_FOR_LOOPS: {sound_naming}") 
    except Exception as e:
        print(f"Error updating SOUND_NAMING_FOR_LOOPS: {e}")






def update_play_loop_fade_time(*args):
    try:
        value = float(play_loop_fade_time_var.get())
        if 0 <= value <= 60:
            settings_manager.set('PLAY_LOOP_FADE_TIME', value)
            play_loop_fade_time_entry.configure(fg_color="#3a3a3a")
            global settings_valid
            settings_valid = True
        else:
            raise ValueError("Value must be between 0 and 60.")
    except (tk.TclError, ValueError):
        play_loop_fade_time_entry.configure(fg_color=color_error_red)
        settings_valid = False




color_error_red = "#880808"


def update_stop_loop_fade_time(*args):
    try:
        value = stop_loop_fade_time_var.get()
        stop_loop_fade_time = float(value)
        if 0 <= stop_loop_fade_time <= 60:
            settings_manager.set('STOP_LOOP_FADE_TIME', stop_loop_fade_time)
            stop_loop_fade_time_entry.configure(fg_color="#3a3a3a")
            global settings_valid
            settings_valid = True
        else:
            raise ValueError("Value must be between 0 and 60.")
    except (tk.TclError, ValueError):
        settings_valid = False
        stop_loop_fade_time_entry.configure(fg_color=color_error_red)



allowed_pattern = re.compile(r'^[A-Za-z0-9_\$,\s]+$')



def update_play_naming(*args):
    text = play_naming_var.get().strip()

    if not text:
        play_naming_entry.configure(fg_color="#3a3a3a")
        global settings_valid
        settings_valid = True
        return

    if not allowed_pattern.match(text):
        play_naming_entry.configure(fg_color=color_error_red)
        settings_valid = False
    else:
        settings_manager.set("PLAY_NAMING_CONVENTION", text)
        play_naming_entry.configure(fg_color="#3a3a3a")
        settings_valid = True



def update_loop_naming(*args):
    global settings_valid
    text = loop_naming_var.get().strip()
    if not text:
        loop_naming_entry.configure(fg_color="#3a3a3a")
        settings_valid = True
        settings_manager.set('NAMING_FOR_LOOPS', text)
        return

    if not re.match(allowed_pattern, text):
        loop_naming_entry.configure(fg_color=color_error_red)
        settings_valid = False
    else:
        settings_manager.set('NAMING_FOR_LOOPS', text)
        settings_valid = True
        loop_naming_entry.configure(fg_color="#3a3a3a")




def update_stop_naming(*args):
    global settings_valid
    text = stop_naming_var.get().strip()
    if not text:
        stop_naming_entry.configure(fg_color="#3a3a3a")
        settings_manager.set('STOP_NAMING_CONVENTION', text)
        settings_valid = True
        return

    if not re.match(allowed_pattern, text):
        stop_naming_entry.configure(fg_color="#880808")
        settings_valid = False
    else:
        settings_manager.set('STOP_NAMING_CONVENTION', text)
        stop_naming_entry.configure(fg_color="#3a3a3a")
        settings_valid = True



def update_capitalize():
    if capitalize_var.get():
        # Uncheck the lowercase checkbox
        lowercase_var.set(False)
    update_letter_case()


def update_lowercase():
    if lowercase_var.get():
        # Uncheck the capitalize checkbox
        capitalize_var.set(False)
    update_letter_case()


class SlidePanel(ctk.CTkFrame):
    def __init__(self, parent, start_pos, end_pos):
        super().__init__(master=parent)
        self.configure(fg_color="#212120")

        self.start_pos = start_pos + 0.04
        self.end_pos = end_pos - 0.03
        self.width = abs(start_pos - end_pos)
        self.pos = self.start_pos
        self.in_start_pos = True

        # Canvas and Frame configuration
        self.canvas = tk.Canvas(self, borderwidth=0, background="#222222")
        self.viewPort = tk.Frame(self.canvas, background="#222222")
        self.viewPort.pack(expand=True, fill='both')

        self.canvas.pack(side="left", fill="both", expand=True)

        # Set the default downward offset:
        top_offset = 30
        self.canvas.create_window(
            (4, 4 + top_offset),
            window=self.viewPort,
            anchor="nw",
            tags="self.viewPort",
            width=325
        )

    def animate(self):
        if self.in_start_pos:
            self.animate_forward()
        else:
            self.animate_backwards()

    def animate_forward(self):
        target_pos = self.end_pos
        self.move_panel(target_pos, False)

    def animate_backwards(self):
        target_pos = self.start_pos
        self.move_panel(target_pos, True)

    def move_panel(self, target_pos, is_starting_position):
        if (self.pos > target_pos and not is_starting_position) or (self.pos < target_pos and is_starting_position):
            self.pos = self.pos - 0.05 if not is_starting_position else self.pos + 0.05
            self.place(relx=self.pos, rely=0.05, relwidth=self.width, relheight=0.93)
            self.after(10, lambda: self.move_panel(target_pos, is_starting_position))
        else:
            self.in_start_pos = is_starting_position


# GUI

window = ctk.CTk()
window.configure(fg_color="#212120")
window.title("Event Creation GUI")
window.geometry("490x600")
window.resizable(False, False)

main_frame = ctk.CTkFrame(window)
main_frame.pack(pady=10)
main_frame.configure(fg_color="#212120")


def refresh_workunit_list():
    global workunit_paths, workunit_names, folder_names
    workunit_paths = get_workunit_path()
    workunit_names = get_workunit_names()
    folder_names = get_folder_names()
    update_workunit_listbox()


def update_workunit_listbox():
    workunit_listbox.delete(0, tk.END)
    for name in workunit_paths:
        workunit_listbox.insert(tk.END, name)


refresh_wwu_icon = ctk.CTkImage(
    light_image=Image.open(Path(__file__).parent / "icons" / "refresh_icon.png"),
    size=(35, 35)
)

refresh_wwu_icon_label = ctk.CTkLabel(window, image=refresh_wwu_icon, text="", cursor="hand2")
refresh_wwu_icon_label.image = refresh_wwu_icon
refresh_wwu_icon_label.lift()
refresh_wwu_icon_label.place(x=12, y=30)
refresh_wwu_icon_label.bind("<Button-1>", lambda _: refresh_workunit_list())

combo_canvas_label = ctk.CTkLabel(window, text="List of available work units and folders", bg_color="#212120", text_color="#9f9f9f")
combo_canvas_label.place(x=60, y=40)

settings_panel = SlidePanel(window, 1.3, 0.4)  # Set start_pos to 1.3
settings_panel.viewPort.columnconfigure(0, weight=3)

# region: Settings widgets
stop_event_var = tk.BooleanVar(value=settings_manager.get('STOP_EVENT_FOR_LOOPS', False))
stop_event_checkbox = ctk.CTkCheckBox(
    settings_panel.viewPort,
    text="Stop Events Loops",
    text_color='white',
    variable=stop_event_var,
    command=update_stop_event_for_loops,
    fg_color="#9f9f9f"
)
# stop_event_checkbox.pack(expand=True, fill='both', padx=2, pady=10)
stop_event_checkbox.grid(row=0, column=0, sticky='w', padx=10, pady=10)

seek_event_var = tk.BooleanVar(value=settings_manager.get('SEEK_ACTION_FOR_LOOPS', False))
seek_event_checkbox = ctk.CTkCheckBox(
    settings_panel.viewPort,
    text="Seek Action Loops",
    text_color='white',
    variable=seek_event_var,
    command=update_seek_event_for_loops,
    fg_color="#9f9f9f"
)
seek_event_checkbox.grid(row=0, column=1, sticky='w', padx=10, pady=10)

letter_case_event_name = settings_manager.get('LETTER_CASE_EVENT_NAME', None)
capitalize_var = tk.BooleanVar(value=(letter_case_event_name == 'upper'))
lowercase_var = tk.BooleanVar(value=(letter_case_event_name == 'lower'))

capitalize_checkbox = ctk.CTkCheckBox(
    settings_panel.viewPort,
    text="Capitalize Events",
    text_color='white',
    variable=capitalize_var,
    command=update_capitalize,
    fg_color="#9f9f9f"
)

lowercase_checkbox = ctk.CTkCheckBox(
    settings_panel.viewPort,
    text="Lowercase Events",
    text_color='white',
    variable=lowercase_var,
    command=update_lowercase,
    fg_color="#9f9f9f"
)

entry_fg_color = "#3a3a3a"
text_color = "White"
label_bg_color = "3a3a3a"

capitalize_checkbox.grid(row=1, column=0, sticky='w', padx=10, pady=10)
lowercase_checkbox.grid(row=1, column=1, sticky='w', padx=10, pady=10)

play_loop_fade_time_label = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Play fade loop [s]",
    text_color=text_color,
    anchor='sw'
)
play_loop_fade_time_label.grid(row=2, column=0, sticky='w', columnspan=4, padx=10)

play_loop_fade_time_var = tk.DoubleVar(value=settings_manager.get('PLAY_LOOP_FADE_TIME', 0.0))
play_loop_fade_time_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=play_loop_fade_time_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
play_loop_fade_time_entry.grid(row=3, column=0, sticky='w', columnspan=4, padx=10)
play_loop_fade_time_var.trace_add("write", update_play_loop_fade_time)

stop_loop_fade_time_label = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Stop fade loop [s]",
    text_color=text_color,
    anchor='sw'
)
stop_loop_fade_time_label.grid(row=2, column=1, sticky='ew', columnspan=3, padx=10)

stop_loop_fade_time_var = tk.DoubleVar(value=settings_manager.get('STOP_LOOP_FADE_TIME', 0.0))
stop_loop_fade_time_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=stop_loop_fade_time_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
stop_loop_fade_time_var.trace_add("write", update_stop_loop_fade_time)
stop_loop_fade_time_entry.grid(row=3, column=1, sticky='ew', columnspan=3, padx=10)

# Loop naming for events
label_loop_naming = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Loops Events Naming",
    text_color=text_color,
    anchor='sw'
)
label_loop_naming.grid(row=6, column=1, sticky='ew', columnspan=3, padx=10)

loop_naming = settings_manager.get('NAMING_FOR_LOOPS', '')
loop_naming_var = tk.StringVar(value=loop_naming)
loop_naming_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=loop_naming_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
loop_naming_var.trace_add("write", update_loop_naming)
loop_naming_entry.grid(row=7, column=1, sticky='ew', columnspan=3, padx=10)

# Loop naming for Sounds
label_loop_sound_naming = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Loops Sound Naming",
    text_color=text_color,
    anchor='se'
)
label_loop_sound_naming.grid(row=6, column=0, sticky='w', columnspan=4, padx=10)

loop_sound_naming_var = tk.StringVar(value=', '.join(settings_manager.get('SOUND_NAMING_FOR_LOOPS', [])))
loop_sound_naming_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=loop_sound_naming_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
loop_sound_naming_var.trace_add("write", update_loop_sound_naming)
loop_sound_naming_entry.grid(row=7, column=0, sticky='w', columnspan=4, padx=10)

play_naming_convention = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Play Events Naming ",
    text_color=text_color,
    anchor='sw'
)
play_naming_convention.grid(row=8, column=0, sticky='ew', columnspan=3, padx=10)

play_naming_var = tk.StringVar(value=settings_manager.get("PLAY_NAMING_CONVENTION", ""))
play_naming_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=play_naming_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
play_naming_entry.grid(row=9, column=0, sticky='ew', columnspan=3, padx=10)
play_naming_var.trace_add("write", update_play_naming)

Stop_naming_convention = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Stop Events Naming ",
    text_color=text_color,
    anchor='sw'
)
Stop_naming_convention.grid(row=10, column=0, sticky='ew', columnspan=3, padx=10)

stop_naming_var = tk.StringVar(value=settings_manager.get("STOP_NAMING_CONVENTION", ""))
stop_naming_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=stop_naming_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
stop_naming_entry.grid(row=11, column=0, sticky='ew', columnspan=3, padx=10)
stop_naming_var.trace_add("write", update_stop_naming)

label_naming_convention = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Source Name",
    text_color=text_color,
    anchor='sw'
)
label_naming_convention.grid(row=12, column=0, sticky='ew', columnspan=3, padx=10)

naming_convention_var = tk.StringVar(value=', '.join(settings_manager.get('NAMING_CONVENTION', [])))
naming_convention_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=naming_convention_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
naming_convention_entry.grid(row=13, column=0, sticky='ew', columnspan=1, padx=10)
naming_convention_var.trace_add("write", update_naming_convention)

label_words_remove = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Words to remove",
    text_color=text_color,
    anchor='sw'
)
label_words_remove.grid(row=12, column=1, sticky='ew', columnspan=3, padx=10)

words_remove_var = tk.StringVar(value=', '.join(settings_manager.get('WORDS_REMOVE', [])))
words_remove_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=words_remove_var,
    fg_color=entry_fg_color,
    text_color=text_color
)
words_remove_entry.grid(row=13, column=1, sticky='ew', columnspan=1, padx=10)
words_remove_var.trace_add("write", update_words_remove)

words_not_capital_Label = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Words to not Capitalize or Lower Case",
    text_color=text_color,
    anchor='sw'
)
words_not_capital_Label.grid(row=14, column=0, sticky='ew', columnspan=3, padx=10)

words_not_capital_Var = tk.StringVar(value=', '.join(settings_manager.get('WORDS_NOT_CAPITALIZE', [])))
words_not_capital_entry = ctk.CTkEntry(
    settings_panel.viewPort,
    textvariable=words_not_capital_Var,
    fg_color=entry_fg_color,
    text_color=text_color
)
words_not_capital_entry.grid(row=15, column=0, sticky='ew', columnspan=3, padx=10)
words_not_capital_Var.trace_add("write", update_words_not_capital)

label_seek_frame = ctk.CTkLabel(
    settings_panel.viewPort,
    text="Seek Values",
    text_color=text_color,
    anchor='sw'
)
label_seek_frame.grid(row=16, column=0, sticky='ew', columnspan=3, padx=10)

frame_seek_values = ctk.CTkFrame(settings_panel.viewPort)
frame_seek_values.configure(fg_color="#212120")
frame_seek_values.grid(row=17, column=0, sticky='ew', columnspan=2, padx=10)

frame_seek_values.columnconfigure(0, weight=1)
frame_seek_values.columnconfigure(1, weight=1)
frame_seek_values.columnconfigure(2, weight=1)

seek_percent_label = ctk.CTkLabel(
    frame_seek_values,
    text="Seek %",
    text_color=text_color,
    anchor='sw'
)
seek_percent_label.grid(row=1, column=0, sticky='ew', columnspan=3, padx=10)

seek_min_label = ctk.CTkLabel(
    frame_seek_values,
    text="Min %",
    text_color=text_color,
    anchor='sw'
)
seek_min_label.grid(row=1, column=1, sticky='ew', columnspan=3, padx=10)

seek_max_label = ctk.CTkLabel(
    frame_seek_values,
    text="Max %",
    text_color=text_color,
    anchor='sw'
)
seek_max_label.grid(row=1, column=2, sticky='ew', columnspan=3, padx=10)


def validate_seek_percent(*args):
    """
    Validation and update of 'seek_percent'.
    Max value is 100.
    """
    global settings_valid
    try:
        value = seek_percent_var.get()
        seek_percent = float(value)
        if seek_percent < 0 or seek_percent > 100:
            raise ValueError("Value must be between 0 and 100.")
        settings_manager.set("SEEK_Percent", seek_percent)
        seek_percent_entry.configure(fg_color="#3a3a3a")
        settings_valid = True
    except (tk.TclError, ValueError):
        settings_valid = False
        seek_percent_entry.configure(fg_color=color_error_red)


def validate_seek_min(*args):
    """
    Validation and update of 'seek_random_min'.
    Min value is -100, max value is 0.
    """
    global settings_valid
    try:
        value = seek_min_var.get()
        seek_random_min = float(value)
        if seek_random_min < -100 or seek_random_min > 0:
            raise ValueError("Value must be between -100 and 0.")
        settings_manager.set("SEEK_RANDOM_MIN", seek_random_min)
        seek_min_entry.configure(fg_color="#3a3a3a")
        settings_valid = True
    except (tk.TclError, ValueError):
        settings_valid = False
        seek_min_entry.configure(fg_color=color_error_red)



def validate_seek_max(*args):
    global settings_valid
    try:
        value = seek_max_var.get()
        seek_random_max = float(value)
        if seek_random_max < 0 or seek_random_max > 100:
            raise ValueError("Value must be between 0 and 100.")
        settings_manager.set("SEEK_RANDOM_MAX", seek_random_max)
        seek_max_entry.configure(fg_color="#3a3a3a")
        settings_valid = True
    except (tk.TclError, ValueError):
        settings_valid = False
        seek_max_entry.configure(fg_color=color_error_red)




seek_percent_var = tk.DoubleVar(value=settings_manager.get("SEEK_Percent", 0.0))
seek_percent_var.trace_add("write", validate_seek_percent)

seek_min_var = tk.DoubleVar(value=settings_manager.get("SEEK_RANDOM_MIN", 0.0))
seek_min_var.trace_add("write", validate_seek_min)

seek_max_var = tk.DoubleVar(value=settings_manager.get("SEEK_RANDOM_MAX", 0.0))
seek_max_var.trace_add("write", validate_seek_max)

seek_percent_entry = ctk.CTkEntry(frame_seek_values, textvariable=seek_percent_var, fg_color=entry_fg_color, text_color=text_color)
seek_percent_entry.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

seek_min_entry = ctk.CTkEntry(frame_seek_values, textvariable=seek_min_var, fg_color=entry_fg_color, text_color=text_color)
seek_min_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

seek_max_entry = ctk.CTkEntry(frame_seek_values, textvariable=seek_max_var, fg_color=entry_fg_color, text_color=text_color)
seek_max_entry.grid(row=2, column=2, sticky="ew", padx=5, pady=5)

# Other widgets in main_frame
toggle_settings_btn = ctk.CTkButton(
    window,
    text="Settings",
    command=settings_panel.animate,
    width=50,
    fg_color="#3a3a3a",
    hover_color="#555555"
)
toggle_settings_btn.place(rely=0.063, relx=0.87)

label_combo = ctk.CTkLabel(main_frame, text=" ", text_color=text_color)
paths_var_string = tk.StringVar()

# Creating a new frame for creation options
create_options_frame = ctk.CTkFrame(main_frame)
create_options_frame.configure(fg_color="#212120")
create_options_frame.grid(row=2, column=0, sticky='nw', padx=10, pady=10)

# Load and resize images
folder_icon = ctk.CTkImage(light_image=Image.open(Path(__file__).parent /"icons"/"foldericon.png"), size=(20, 20))
wwu_icon = ctk.CTkImage(light_image=Image.open(Path(__file__).parent /"icons"/"workuniticon.png"), size=(20, 20))

# Keep references
window.folder_icon = folder_icon
window.wwu_icon = wwu_icon

entry_str_new_parent = tk.StringVar()

entry_label_new_wwu = ctk.CTkLabel(
    create_options_frame,
    text=" New work unit name:",
    text_color="white",
    image=wwu_icon,
    compound="left"
)
entry_new_wwu_name = ctk.CTkEntry(
    create_options_frame,
    textvariable=entry_str_new_parent,
    width=150,
    fg_color="#212120",
    text_color="White"
)

# IntVar to track the checkbox state
show_entry_new_wwu_var = tk.IntVar(value=0)


def toggle_visibility_wwu_entry():
    if show_entry_new_wwu_var.get() == 1:
        show_entry_new_folder_var.set(0)
        entry_label_new_folder.grid_forget()
        entry_new_folder_name.grid_forget()
        entry_new_folder_name.delete(0, "end")
        entry_label_new_wwu.grid(row=4, column=0, pady=5, sticky='w')
        entry_new_wwu_name.grid(row=5, column=0, pady=5, sticky='w')
    else:
        entry_label_new_wwu.grid_forget()
        entry_new_wwu_name.grid_forget()
        entry_new_wwu_name.delete(0, "end")


show_new_wwu_checkbox = ctk.CTkCheckBox(
    create_options_frame,
    text="Create new wwu",
    variable=show_entry_new_wwu_var,
    command=toggle_visibility_wwu_entry,
    width=35,
    text_color='White',
    fg_color="#9f9f9f"
)

entry_label_new_folder = ctk.CTkLabel(
    create_options_frame,
    text=" New folder name:",
    text_color="white",
    image=folder_icon,
    compound="left"
)
entry_new_folder_name = ctk.CTkEntry(
    create_options_frame,
    textvariable=entry_str_new_parent,
    width=150,
    fg_color="#212120",
    text_color="White"
)

show_entry_new_folder_var = tk.IntVar(value=0)


def toggle_visibility_folder_entry():
    if show_entry_new_folder_var.get() == 1:
        show_entry_new_wwu_var.set(0)
        entry_label_new_wwu.grid_forget()
        entry_new_wwu_name.grid_forget()
        entry_new_wwu_name.delete(0, "end")
        entry_label_new_folder.grid(row=4, column=0, pady=5, sticky='w')
        entry_new_folder_name.grid(row=5, column=0, pady=5, sticky='w')
    else:
        entry_label_new_folder.grid_forget()
        entry_new_folder_name.grid_forget()
        entry_new_folder_name.delete(0, "end")


show_new_folder_checkbox = ctk.CTkCheckBox(
    create_options_frame,
    text="Create new folder",
    variable=show_entry_new_folder_var,
    command=toggle_visibility_folder_entry,
    width=35,
    text_color='White',
    fg_color="#9f9f9f"
)

label_combo.grid(row=0, column=0, columnspan=3, sticky='w', padx=15, pady=15)
show_new_wwu_checkbox.grid(row=2, column=0, pady=5, sticky='w')
show_new_folder_checkbox.grid(row=3, column=0, pady=5, sticky='w')

create_events_icon = ctk.CTkImage(light_image=Image.open(Path(__file__).parent /"icons"/"wwise_logo.png"), size=(60, 45))
window.create_events_icon = create_events_icon

launch_button = ctk.CTkButton(
    main_frame,
    text="Create Events",
    command=handle_create_events,
    image=create_events_icon,
    compound="left",
    fg_color="#3a3a3a",
    hover_color="#555555",
    text_color="white",
    width=200,
    height=50,
    font=("Arial", 16)
)
launch_button.grid(row=3, column=0, columnspan=1, sticky='ws')


def filter_workunits(*args):
    query = search_var.get().lower()
    filtered = [path for path in workunit_paths if query in path.lower()]
    workunit_listbox.delete(0, tk.END)
    for path in filtered:
        workunit_listbox.insert(tk.END, path)


# Search bar
search_var = tk.StringVar()
search_var.trace_add("write", filter_workunits)



listbox_frame = ctk.CTkFrame(main_frame, fg_color="#212120", border_color="#212120", border_width=2)
scrollbar = tk.Scrollbar(listbox_frame)
workunit_listbox = tk.Listbox(
    listbox_frame,
    yscrollcommand=scrollbar.set,
    width=5,
    bg="#333333",
    fg="white",
    selectbackground="#555555",
    selectforeground="Black",
    highlightthickness=0  # Remove the default listbox border
)
listbox_frame.grid(row=1, column=0, sticky='nsew', columnspan=3, pady=15)

search_entry = tk.Entry(listbox_frame, textvariable=search_var, bg="#333333", font=("Arial", 20), width=32)
search_entry.pack(fill='both')

workunit_listbox.pack(expand=True, fill='both')

listbox_evets_frame = ctk.CTkFrame(main_frame)
listbox_evets_frame.configure(fg_color='#212120')

listbox_evets_frame = ctk.CTkFrame(main_frame)
listbox_evets_frame.configure(fg_color='#212120')
scrollbar_events = tk.Scrollbar(listbox_evets_frame)
created_events_listbox = tk.Listbox(
    listbox_evets_frame,
    yscrollcommand=scrollbar_events.set,
    width=40,
    bg="#222222",
    fg="#9f9f9f",
    selectbackground="#555555",
    selectforeground="Black",
    highlightthickness=0
)

# label "Created Items" above the listbox
created_items_label = ctk.CTkLabel(
    listbox_evets_frame,
    text="Created Items",
    bg_color="#212120",
    text_color="#9f9f9f"
)
created_items_label.grid(row=0, column=0, columnspan=2, sticky='ewn')
created_events_listbox.grid(row=1, column=0, sticky='nsew', columnspan=5)


listbox_evets_frame.grid(row=2, column=2, sticky='nsew', padx=10)


def clear_created_events_listbox(event=None):
    """
    Clear the created_events_listbox content.
    For example, you can also reset global lists in the code:
    # created_events.clear()
    # created_event_seek_names.clear()
    # optionally reset the "Created Items" label if you want
    """
    created_events_listbox.delete(0, tk.END)


# Trash icon
trash_image = Image.open(Path(__file__).parent/ "icons"/"trash_icon.png")
trash_image_resized = trash_image.resize((20, 20))
trash_icon = ImageTk.PhotoImage(trash_image_resized)

trash_icon = ctk.CTkImage(
    light_image=Image.open(Path(__file__).parent / "icons" / "trash_icon.png"),
    size=(20, 20)
)
window.trash_icon = trash_icon 

trash_label = ctk.CTkLabel(
    listbox_evets_frame,
    image=trash_icon,
    text="",          
    fg_color="#212120", 
    cursor="hand2"
)
trash_label.grid(row=0, column=1, sticky='e', padx=(0, 5))

# click binding to the clearing function
trash_label.bind("<Button-1>", clear_created_events_listbox)

listbox_evets_frame.grid_columnconfigure(0, weight=1)  
listbox_evets_frame.grid_rowconfigure(0, weight=1)


def update_events_listbox(display_text, object_id):
    # Save to the global dictionary
    created_items_dict[display_text] = object_id

    # Add to the listbox (so the user can see the text)
    if display_text not in created_events_listbox.get(0, tk.END):
        created_events_listbox.insert(tk.END, display_text)

    if created_events_listbox.size() == 1:
        # Show label, etc.
        pass


def return_events_listbox(listbox):
    return listbox.get(0, tk.END)


def select_object_in_wwise(object_name):
    try:
        global client
        options = {
            "return": [
                "path",
                "id",
                "isPlayable",
                "originalWavFilePath",
                "parent.id",
                "ChannelConfigOverride",
                "name"
            ]
        }
        query_result = client.call(
            "ak.wwise.core.object.get",
            {"waql": f"$ from type event, workunit, folder where name = \"{object_name}\" where path: \"events\""},
            options=options
        )
        item_name = (query_result['return'][0]['id'])
        item_path = (query_result['return'][0]['path'])
        print(item_path)
        print([item_name])

        client.call("ak.wwise.ui.commands.execute", {
            "command": "FindInProjectExplorerSelectionChannel1",
            "objects": [item_name]
        })

    except Exception as e:
        print(f"Error in selecting object in Wwise: {e}")


def on_listbox_select(event):
    """
    Handles <<ListboxSelect>> events from both 'created_events_listbox' and 'workunit_listbox'.
    It checks which widget triggered the event (event.widget).
    """
    widget = event.widget


    if widget == created_events_listbox:
        selection_index = created_events_listbox.curselection()
        if selection_index:
            selected_display_text = created_events_listbox.get(selection_index[0])

            if selected_display_text in created_items_dict:
                wwise_id = created_items_dict[selected_display_text]
                try:
                    global client
                    client.call("ak.wwise.ui.commands.execute", {
                        "command": "FindInProjectExplorerSelectionChannel1",
                        "objects": [wwise_id]
                    })
                except Exception as e:
                    print(f"Error in selecting object in Wwise: {e}")


    elif widget == workunit_listbox:
        selection_index = workunit_listbox.curselection()
        if selection_index:
            selected_item = workunit_listbox.get(selection_index[0])

            paths_var_string.set(selected_item)


# Bind the selection event of the listbox to on_listbox_select
created_events_listbox.bind('<<ListboxSelect>>', on_listbox_select)


def copy_to_clipboard(event):
    # Get the index of the selected item
    selection_index = created_events_listbox.curselection()
    if selection_index:
        selected_text = created_events_listbox.get(selection_index[0])
        window.clipboard_clear()
        window.clipboard_append(selected_text)
        


workunit_listbox.bind('<<ListboxSelect>>', on_listbox_select)

project_label = ctk.CTkLabel(
    main_frame,
    text=f"Not Connected",
    text_color="#9f9f9f",
    anchor="e"
)
project_label.grid(row=3, column=2, padx=15, sticky='es')
icon_path = Path(__file__).parent / "icons" / "warpp_logo_black.ico"
window.iconbitmap(str(icon_path))

window.grid_columnconfigure(0, weight=4)
window.grid_columnconfigure(1, weight=1)

def on_close():
    close_waapi_connection()  
    window.destroy()        

def main():
    global client
    client = open_waapi_connection()

    
    global workunit_names, workunit_paths, folder_names
    workunit_names = get_workunit_names()
    workunit_paths = get_workunit_path()
    folder_names = get_folder_names()
    
    project_name = "Not Connected"
    try:
        info = client.call("ak.wwise.core.getProjectInfo")
        project_name = info.get("name", "Not Connected")
    except Exception:
        pass
    project_label.configure(text=project_name)
    
    for name in workunit_paths:
        workunit_listbox.insert(tk.END, name)

    # tool version
    version_label = ctk.CTkLabel(window, text="v1.0.0", text_color="#9f9f9f")
    version_label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)
    
    window.protocol("WM_DELETE_WINDOW", on_close)

    #Run gui
    window.mainloop()

        

if __name__ == "__main__":
    main()