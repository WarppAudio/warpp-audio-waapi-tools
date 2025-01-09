# 🎮 Wwise Event Creation Tool

## 📋 Setup

Before using the tool, ensure that:
- You have installed all requirements from the main repository
- The `settings.JSON` file is placed in the same directory as `main.py`

> **Note**: All settings are automatically saved whenever you make changes in the tool's interface

## 🖥️ Tool Documentation

### 🎯 Main Interface


![event_creation_main_section](https://github.com/user-attachments/assets/7333dd35-cbae-499e-abea-9093c1846f13)


1. **Refresh Button**

- This button refreshes the list of Work Units and folders displayed in the tool.

- It is useful when changes are made directly in Wwise (e.g., adding or deleting Work Units or folders) to ensure the tool reflects the most up-to-date project structure.

2. **Settings**

- Opens the Settings Panel, where users can configure detailed options for event creation, such as naming conventions, fade times, and behavior for loops or seek actions.

3. **List of Available Work Units and Folders**

- Displays the current hierarchy of Work Units and folders under the "Events" category in Wwise.

- Users can browse, select, or filter through this list to choose where new Work Units, folders, or events will be created.

- Reflects changes after using the Refresh Button (Point 1).

4. **Create new wwu / Create new folder**

- These checkboxes allow users to specify whether they want to create a new Work Unit or a new folder within the selected location in Wwise:

- Create new wwu: Allows entering a name for a new Work Unit in the input field below (New work unit name).

- Create new folder: Enables the creation of a new virtual folder in the selected location.

- Only one of these options can be enabled at a time.

5. **Created Items**

- Displays a list of all items created during the current session, such as:

- Work Units ([W]),

- Events ([E]).

- Includes a trash icon that allows users to clear the list of created items.

- Clicking on an item selects it in Wwise.

6. **Create Events**

- The main button to trigger the creation process based on the current selection, settings, and input values.

- Executes the following actions:

- Creates new events (Play/Stop/Seek) for selected objects in Wwise.

- Adds new Work Units or folders (if configured).

- Applies naming conventions and settings specified in the tool.

7. **Project Name**

- Displays the name of the connected Wwise project (test-waapi-2024 in this case).

- Helps users confirm that the tool is connected to the correct Wwise project.

### ⚙️ Settings Panel

![event_creation_settings_section](https://github.com/user-attachments/assets/87c62c69-2cdc-4aa0-ac77-f00cc0325571)

1. **Stop Events Loops**

- This checkbox enables or disables the automatic creation of "Stop" events for looping sounds.

- If checked, the tool will automatically generate events to stop loops.

2. **Seek Action Loops**

- This checkbox enables or disables the creation of "Seek" actions for looping sounds.

- If checked, the tool will add seek events for loops, starting playback at a specific percentage.

3. **Capitalize Events / Lowercase Events**

- These checkboxes allow you to set either capitalize or lowercase formatting for event names (mutually exclusive).

- Capitalize Events: Ensures that the first letter of each word in the event name is uppercase.

- Lowercase Events: Ensures that all letters in the event name are lowercase.

4. **Play fade loop [s]**

- This field defines the fade-in duration (in seconds) for "Play" actions when starting looping sounds.

- The value determines how smoothly the sound starts playing.

5. **Stop fade loop [s]**

- This field specifies the fade-out duration (in seconds) for "Stop" actions when stopping looping sounds.

- The value ensures smooth sound transitions when stopping.

6. **Loops Sound Naming**

- This field allows specifying keywords or suffixes (e.g., _lp, _loop) that identify looping sounds.

- The tool uses these case-sensitive keywords to detect loops during event creation.

7. **Loops Events Naming**

- This field defines the naming convention for loop-related events.

- For example, _Loop can be appended to event names to signify they are associated with loops.

8. **Play Events Naming**

- This field defines the prefix for "Play" events.

- For example, Play_ will be added to event names to follow a consistent naming convention.

9. **Stop Events Naming**

- This field defines the prefix for "Stop" events.

- For example, Stop_ will be added to event names related to stopping playback.

10. **Source Name**

- This field specifies naming conventions that the original file names must follow.

- If a sound's name does not contain at least one of the listed conventions, an error message will be displayed. However, events will still be created, even if the naming convention is not matched.

11. **Words to remove**

- This field lists words or fragments to be removed from event names during the creation process.

- For example, sfx will be stripped from any names containing it.

12. **Words to not Capitalize or Lower Case**

- This field lists specific words that should not be altered when formatting event names.

- For example, AMB, ENM will remain unchanged in the final event names.

13. **Seek Values (Seek %, Min %, Max %)**

- Seek %: Defines the default starting percentage for "Seek" actions in loops.

- Min %: Sets the minimum percentage for randomization of the "Seek" action.

- Max %: Sets the maximum percentage for randomization of the "Seek" action.

- These values determine how the playback position is randomized in looping events.
