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
            base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
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


def format_event_name(name, prefix, settings_manager):

    # Formats the event name according to various settings:
    #  - Replaces spaces and dashes with underscores
    #  - Removes extra underscores
    #  - Splits the name into words separated by underscores
    #  - Skips capitalization or lowercasing for certain words:
    #    + Direct match in the 'words_not_capital' list
    #    + Matches any regex pattern created from 'words_not_capital' items containing '#'
    #      (for example, "SFX#" -> regex ^SFX\d+$)
    #  - Applies uppercase or lowercase if specified in settings
    #  - Finally, adds a prefix and returns the resulting string


    # Retrieve settings
    words_not_capital = settings_manager.get('WORDS_NOT_CAPITALIZE', [])
    letter_case_event_name = settings_manager.get('LETTER_CASE_EVENT_NAME', None)
    loop_naming = settings_manager.get('NAMING_FOR_LOOPS', '')

    # Prepare two lists:
    # 1) direct_words: items from 'words_not_capital' that do not contain '#'
    # 2) regex_words: items that do contain '#'; we convert them into regex patterns
    direct_words = []
    regex_words = []

    for item in words_not_capital:
        item_strip = item.strip()
        if '#' in item_strip:
            # Replace '#' with \d+ to match any sequence of digits
            # For example: "SFX#" -> '^SFX\d+$'
            pattern = '^' + item_strip.replace('#', r'\d+') + '$'
            try:
                # Compile the regex pattern
                compiled = re.compile(pattern)
                regex_words.append(compiled)
            except Exception:
                # If the pattern is invalid, skip it or log an error
                continue
        else:
            direct_words.append(item_strip)

    # Replace spaces and dashes with underscores and remove consecutive underscores
    name = name.replace(' ', '_').replace('-', '_')
    name = re.sub(r'__+', '_', name)

    # Split the name on underscores
    words = name.strip('_').split('_')

    formatted_words = []
    for word in words:
        word_stripped = word.strip()

        # Determine if this word should skip any capitalization/lowercase modifications
        skip_capitalization = False

        # Condition 1: The word is in direct_words
        # Condition 2: The word matches loop_naming (existing logic)
        if word_stripped in direct_words or word_stripped in loop_naming:
            skip_capitalization = True
        else:
            # Check each compiled regex from regex_words
            for rgx in regex_words:
                if rgx.match(word_stripped):
                    skip_capitalization = True
                    break

        # If skip_capitalization is True, we keep the word exactly as is
        if skip_capitalization:
            formatted_words.append(word_stripped)
        else:
            # Otherwise, apply uppercase or lowercase rules if configured
            if letter_case_event_name == 'upper':
                formatted_words.append(word_stripped.capitalize())
            elif letter_case_event_name == 'lower':
                formatted_words.append(word_stripped.lower())
            else:
                # If None, leave the word as-is
                formatted_words.append(word_stripped)

    # Rebuild the name with underscores
    formatted_name = '_'.join(formatted_words)

    # Prefix the name and remove any trailing underscores
    formatted_name = f"{prefix}{formatted_name}".strip('_')

    return formatted_name





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

        # Build the pattern allowing ^ (start), _ (underscore), or - (dash) on the left,
        # and _ (underscore), - (dash), or $ (end) on the right.
        # We do NOT use re.IGNORECASE, so it is case sensitive.
        pattern = re.compile(r'(?:^|_|-)' + token_escaped + r'(?:_|-|$)')

        # If the pattern matches anywhere in the sound_name, return True immediately
        if pattern.search(sound_name):
            return True
    return False

def create_event_play(name, target, client, is_loop=False):
    play_naming = settings_manager.get("PLAY_NAMING_CONVENTION", "")
    event_name = format_event_name(name, play_naming, settings_manager)
    play_loop_fade_time = settings_manager.get("PLAY_LOOP_FADE_TIME", 0.0)

    if event_exists(event_name, client):
        print(f"[SKIP] Event '{event_name}' already exists in project, skipping.")
        return None

    # prepar play action
    action = {
        "type": "Action",
        "@ActionType": 1,
        "name": "Start",
        "@Target": target
    }
    # if it's loot set fade time
    if is_loop:
        action["@FadeTime"] = play_loop_fade_time

    event = {
        "type": "Event",
        "name": event_name,
        "children": [action]
    }
    return event





def create_event_stop(name, target, client):
    stop_naming = settings_manager.get("STOP_NAMING_CONVENTION", "")
    event_name = format_event_name(name, stop_naming, settings_manager)
    stop_loop_fade_time = settings_manager.get("STOP_LOOP_FADE_TIME", 0.0)

    if event_exists(event_name, client):
        print(f"[SKIP] Event '{event_name}' already exists in project, skipping.")
        return None

    event = {
        "type": "Event",
        "name": event_name,
        "children": [
            {
                "type": "Action",
                "@ActionType": 2,
                "@FadeTime": stop_loop_fade_time,
                "name": "",
                "@Target": target
            },
        ]
    }
    return event



def create_event_seek(name, target, client):
    play_naming = settings_manager.get("PLAY_NAMING_CONVENTION", "")
    event_name = format_event_name(name, play_naming, settings_manager)
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

def create_play_or_seek_event(path_obj, target_id, is_loop, client):
    seek_event_for_loops = settings_manager.get('SEEK_ACTION_FOR_LOOPS', False)
    if is_loop and seek_event_for_loops:
        # 'Seek' event creation
        return create_event_seek(str(path_obj.stem), target_id, client)
    else:
        # "Play" event creation, and pass is_loop info
        return create_event_play(str(path_obj.stem), target_id, client, is_loop)





def create_events_for_selection(wwu_path, new_wwu):
    """
    Creates events (Play/Seek + optional Stop) based on the current Wwise selection.
    Places them inside the specified wwu_path + new_wwu, ignoring the original path location.
    """
    global client
    try:
        
            # Retrieve currently selected Wwise objects
        options = {
            "return": [
                "path",
                "id",
                "isPlayable",
                "originalWavFilePath",
                "parent.id",
                "ChannelConfigOverride",
                "name",
            ]
        }
        selected_objs = client.call(
            "ak.wwise.ui.getSelectedObjects", {}, options=options
        )["objects"]

        # We'll collect event dictionaries in set_args["objects"]
        set_args = {
            "objects": [],
            "onNameConflict": "merge",
        }

        newly_created_event_names = []
        incorrect_sources = []

        # get actual info
        words_remove = settings_manager.get('WORDS_REMOVE', [])
        loop_sound_naming = settings_manager.get('SOUND_NAMING_FOR_LOOPS', [])
        naming_convention = settings_manager.get('NAMING_CONVENTION', [])
        loop_naming = settings_manager.get('NAMING_FOR_LOOPS', '')
        stop_event_for_loops = settings_manager.get('STOP_EVENT_FOR_LOOPS', False)
        seek_random_min = settings_manager.get("SEEK_RANDOM_MIN", 0.0)
        seek_random_max = settings_manager.get("SEEK_RANDOM_MAX", 0.0)

        for obj in selected_objs:
            # Skip anything that's not playable
            if not obj["isPlayable"]:
                continue

            original_name = obj["name"]

            # Remove words from the name (words_remove)
            cleaned_name = original_name
            for w in words_remove:
                cleaned_name = cleaned_name.replace(w, "")
            cleaned_name = re.sub(r"_+", "_", cleaned_name).strip("_")

            # Check if the name indicates a loop 
            # (we look for items in loop_sound_naming)
            is_loop = check_if_is_loop_sound(cleaned_name, loop_sound_naming)

            if is_loop:
                # remove tokens from the name
                for token in loop_sound_naming:
                    cleaned_name = cleaned_name.replace(token, "")
                cleaned_name = re.sub(r"_+", "_", cleaned_name).strip("_")
                
                # Also remove the existing loop_naming if present, then reappend it
                cleaned_name = cleaned_name.replace(loop_naming, "").strip("_")
                cleaned_name = f"{cleaned_name}_{loop_naming}".strip("_")

            # Build children events (Play/Seek + optional Stop)
            children = []

            play_event = create_play_or_seek_event(Path(cleaned_name), obj["id"], is_loop, client)
            if play_event:
                children.append(play_event)
                newly_created_event_names.append(play_event["name"])

            # Optionally create a Stop event for loops if setting is enabled
            if is_loop and stop_event_for_loops:
                stop_evt = create_event_stop(cleaned_name, obj["id"], client)
                if stop_evt:
                    children.append(stop_evt)
                    newly_created_event_names.append(stop_evt["name"])

            # Attach these events to the chosen WorkUnit/folder
            set_args["objects"].append({
                "object": wwu_path + "\\" + new_wwu,
                "children": children,
            })

            # Check if the AudioFileSource naming matches the naming_convention
            audio_source_query = {
                "waql": f'$ "{obj["id"]}" select this, descendants where type = "AudioFileSource"'
            }
            sources = client.call("ak.wwise.core.object.get", audio_source_query, options=options)
            for source_item in sources["return"]:
                source_name = source_item["name"]
                if not any(conv in source_name for conv in naming_convention):
                    incorrect_sources.append(source_name)


        # Actually create these objects in Wwise
        client.call("ak.wwise.core.object.set", set_args)

        # Retrieve the newly created event IDs and update the listbox
        for e_name in newly_created_event_names:
            event_query = {
                "waql": f'$ from type Event where name = "{e_name}"'
            }
            get_options = {"return": ["id", "name", "path"]}
            res = client.call("ak.wwise.core.object.get", event_query, options=get_options)

            found = res.get("return", [])
            if not found:
                continue

            wwise_id = found[0]["id"]
            display_text = f"{e_name} [E]"
            update_events_listbox(display_text, wwise_id)

        # Handle randomization for any Seek events that were created
        for event_name in created_event_seek_names:
            seek_query = {
                "waql": f'$ from object "Event:{event_name}" select children where actiontype = 36'
            }
            seek_actions = client.call("ak.wwise.core.object.get", seek_query, options=options)
            for seek_item in seek_actions["return"]:
                action_id = seek_item.get("id")
                random_args = {
                    "object": str(action_id),
                    "enabled": True,
                    "property": "SeekPercent",
                    "min": seek_random_min,
                    "max": seek_random_max,
                }
                client.call("ak.wwise.core.object.setRandomizer", random_args)

        # If there are any sources that do not match the naming convention, show error
        if incorrect_sources and len(naming_convention) > 0:
            root = tk.Tk()
            root.withdraw()
            incorrect_sources_message = "\n".join(incorrect_sources)
            messagebox.showerror(
                "Error",
                f"Incorrect naming convention. The .wav file name should contain {naming_convention}.\n"
                f"Incorrect source names:\n{incorrect_sources_message}",
            )

    except Exception as e:
        traceback.print_exc()
        print(str(e))




def get_workunit_path():
    global client
    # Define the options for the query
    options = {"return": ["path", "id", "isPlayable", "originalWavFilePath", "parent.id", "ChannelConfigOverride", "name", "type"]}

    # Query for workunits
    wwu_query = {
        'waql': '$ from type workunit where category = "Events"',
    }
    wwu_result = client.call("ak.wwise.core.object.get", wwu_query, options=options)

    # Query for folders
    folder_query = {
        'waql': '$ from type folder where category = "Events"',
    }
    folder_result = client.call("ak.wwise.core.object.get", folder_query, options=options)

    # Combine the results
    combined_results = wwu_result.get('return', []) + folder_result.get('return', [])

    # Extract paths
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

    # (1) Check name uniqueness across the entire project (WorkUnits)
    for wwu_name, wwu_path in all_wwu:
        if wwu_name.lower() == new_name.lower():
            return False  # A WorkUnit with the same name already exists

    # (2) Check if there's no Folder with the same name in the same parent_path
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

    # 1. Attempt to create a Folder
    if show_entry_new_folder_var.get() == 1 and new_parent_name:
        if not can_create_folder(new_parent_name, workunit_path):
            messagebox.showinfo(
                "Virtual Folder Name Conflict",
                f"Object with name: {new_parent_name}, already exists in this location"
            )
            return  # silent return -> nothing is created, no events
        else:
            create_new_folder(workunit_path, new_parent_name)

    # 2. Attempt to create a WorkUnit
    if show_entry_new_wwu_var.get() == 1 and new_parent_name:
        if not can_create_workunit(new_parent_name, workunit_path):
            messagebox.showinfo("Work Unit Name Conflict", f"Work Unit: {new_parent_name}, already exists")
            return  # silent return
        else:
            create_new_workunit(workunit_path, new_parent_name)

    # 3. If we got here, it means:
    #    - user did not check anything to create
    #    - or we successfully created a Folder/WorkUnit without conflicts
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
        
        print(f"Updated SOUND_NAMING_FOR_LOOPS: {sound_naming}")  # Logowanie dla debugowania
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



allowed_pattern = re.compile(r'^[A-Za-z0-9_]+$')


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

# We place listbox_evets_frame in column 2
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

# We add a click binding to the clearing function
trash_label.bind("<Button-1>", clear_created_events_listbox)

listbox_evets_frame.grid_columnconfigure(0, weight=1)  # Makes the listbox expand horizontally
listbox_evets_frame.grid_rowconfigure(0, weight=1)


def update_events_listbox(display_text, object_id):
    # Save to the global dictionary
    created_items_dict[display_text] = object_id

    # Add to the listbox (so the user can see the text)
    if display_text not in created_events_listbox.get(0, tk.END):
        created_events_listbox.insert(tk.END, display_text)

    # If you wanted to set label/scrollbar visibility here, etc., you can keep the existing logic, e.g.:
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
            "command": "FindInProjectExplorerSyncGroup1",
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

    # 1. If the event came from created_events_listbox
    if widget == created_events_listbox:
        selection_index = created_events_listbox.curselection()
        if selection_index:
            selected_display_text = created_events_listbox.get(selection_index[0])
            # if the text exists in dictionary created_items_dict:
            if selected_display_text in created_items_dict:
                wwise_id = created_items_dict[selected_display_text]
                try:
                    global client
                    client.call("ak.wwise.ui.commands.execute", {
                        "command": "FindInProjectExplorerSyncGroup1",
                        "objects": [wwise_id]
                    })
                except Exception as e:
                    print(f"Error in selecting object in Wwise: {e}")

    # 2. If the event came from workunit_listbox
    elif widget == workunit_listbox:
        selection_index = workunit_listbox.curselection()
        if selection_index:
            selected_item = workunit_listbox.get(selection_index[0])
            # Update the variable so user can see the path in entry or do other logic
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


project_name = "Not Connected"
try:
    #global client
    info = client.call("ak.wwise.core.getProjectInfo")
    project_name = info.get("name", "Not Connected")
except Exception:
    pass

project_label = ctk.CTkLabel(
    main_frame,
    text=f"{project_name}",
    text_color="#9f9f9f",
    anchor="e"
)
project_label.grid(row=3, column=2, padx=15, sticky='es')
icon_path = Path(__file__).parent / "icons" / "warpp_logo_white.ico"
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
    
    for name in workunit_paths:
        workunit_listbox.insert(tk.END, name)

    window.protocol("WM_DELETE_WINDOW", on_close)

    try:
    # Run gui
        window.mainloop()
    finally:
    # Closing connection
        close_waapi_connection()

if __name__ == "__main__":
    main()