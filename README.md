# 🎵 Wwise Python Tools - General Setup

Welcome to the **warpp-audio-waapi-tools** repository! This project is a collection of Python-based tools that leverage the **Wwise Authoring API (WAAPI)** to streamline and automate tasks within Audiokinetic Wwise.

## 🚀 Getting Started

These instructions will guide you through the setup required to run any tool in this repository.

## 🔧 Requirements

- **Python 3.8+**
- **Wwise 2022.1.x +**
- **Wwise Authoring API** enabled in your Wwise project:
  - Go to `Project > User Preferences` and enable **Wwise Authoring API**
- **WAAPI Client for Python** installed (details below)

## 🛠 Installation Steps

### 1️⃣ Install Python

Download and install Python from the [official Python website](https://www.python.org/downloads/).

> **Important**: During installation, make sure to check "Add Python to PATH" to enable running Python from any command prompt

Verify your installation by opening Command Prompt or Terminal and running:

```bash
python --version
```

### 2️⃣ Installing the Command Add-ons (2022.1x+)

If you want the tools to be available in every Wwise installation and project:
- Navigate to the `%APPDATA%/Audiokinetic/Wwise/Add-ons` directory
- If the `Add-ons` folder does not exist, create it
- For other installation methods, watch [this video](https://youtu.be/7LpANxZD1cE?si=pCo8zNlsRYKFv5zi&t=60) or read [this document](https://www.audiokinetic.com/fr/library/edge/?source=SDK&id=defining_custom_commands.html)

Download this whole repository zip file from GitHub.

Unzip the contents of the warpp-audio-waapi-tools folder into the Add-ons directory.

> **Important**: If you already have an existing Commands folder with a '.json' file for commands, move the '.json' file from this repository into your existing Commands folder to avoid overwriting your current file.

Install the required dependencies using the following command:

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes essential libraries:
- **waapi-client**: Communicates with Wwise via WAAPI
- **customtkinter**
- **Pillow**

Restart Wwise or use the command Reload Commands (Ctrl + Shift + K)

## 🎓 Additional Resources

- [Learn about WAAPI](https://www.audiokinetic.com/library/edge/?source=SDK&id=waapi.html)
- [Using Python with WAAPI](https://www.audiokinetic.com/library/edge/?source=SDK&id=waapi_client_python_rpc.html)
- [Command Add-ons in Wwise](https://www.audiokinetic.com/library/edge/?source=SDK&id=defining_custom_commands.html)

## 📬 Feedback & Contributions

Have suggestions or found a bug? Feel free to open an issue or submit a pull request!

Happy automating! 🎮 🎵
