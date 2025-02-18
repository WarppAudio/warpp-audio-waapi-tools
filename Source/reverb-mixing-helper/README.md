# 🎚️ Reverb Mixing Helper

A powerful tool designed to streamline the process of auditioning and mixing aux/reverb sends in Wwise. This utility allows for quick testing of multiple sounds through various reverb configurations, significantly speeding up your audio workflow.

## ✨ Features

- 🎯 **AUX Send Tracking**: Automatically assigns selected aux buses to loaded sounds
- 🔄 **Sequence Mode**: Play sounds sequentially with customizable delays
- 🔁 **Loop Control**: Individual loop toggles for each sound
- 🎮 **Playback Controls**: Independent play/stop controls for each sound

![image](https://github.com/user-attachments/assets/6ad4a75a-0f2c-4c53-a774-6bebb8ba094a)


## 🚀 Getting Started

### Prerequisites
- Wwise installed and running
- WAAPI enabled in Wwise preferences
- Python with required dependencies:
  - `customtkinter`
  - `waapi`

### Important Notes

⚠️ **Before You Begin**:
- It's recommended to move sounds you want to test into a separate/test work unit

### 📥 Loading Sounds

1. Add sound slots using the "Add" button in the control panel
2. Copy sound GUIDs from Wwise (SHIFT + Right-click → Copy GUID(s) to clipboard)
3. Paste GUIDs into the sound slots

![image](https://github.com/user-attachments/assets/0cd2ac99-8471-45e4-8dbc-61f9f37d153f)


## 🎛️ Interface Guide

![image](https://github.com/user-attachments/assets/7f63664c-0113-4272-a59b-3a07daecea89)


### 1. AUX Tracking Section
- Toggle button to start/stop AUX tracking
- Displays currently selected AUX bus name
- Visual indicator showing tracking status

### 2. Control Panel
- Add: Creates new sound slots
- Stop All: Stops all playing sounds
- Delay(ms): Sets interval between sequential playback
- Sequence: Enables sequential playback mode

### 3. Sound List
- Displays added sounds with their names
- Shows sound GUIDs and corresponding Wwise object names

### 4. Sound Controls
- Play/Stop: Individual playback control
- Loop: Toggle sound looping
- Delete: Remove sound from list

### 5. Footer
- Shows current Wwise project name
- Displays tool version

## 🛠️ Usage Tips

1. **AUX Testing Workflow**:
   - Load your sounds
   - Enable AUX tracking
   - Select different aux buses in Wwise to automatically update sends

2. **Sequential Testing**:
   - Enable Sequence mode
   - Set desired delay between sounds
   - Press play on any sound to start the sequence

3. **Quick Auditioning**:
   - Use individual loop toggles for continuous playback
   - Combine with sequence mode for complex testing patterns

## 🔄 Version
Current version: v1.0.0

