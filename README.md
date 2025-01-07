
# 🎵 Wwise Python Tools - General Setup

Welcome to the **warpp-audio-waapi-tools** repository! This project is a collection of Python-based tools that leverage the **Wwise Authoring API (WAAPI)** to streamline and automate tasks within Audiokinetic Wwise.

## 🚀 Getting Started

These instructions will guide you through the setup required to run any tool in this repository.

---

## 🔧 Requirements

- **Python 3.8+**
- **Wwise 2022.1.x +**
- **Wwise Authoring API** enabled in your Wwise project:
  - Go to `Project > User Preferences` and enable **Wwise Authoring API**.
- **WAAPI Client for Python** installed (details below).

---

## 🛠 Installation Steps

### 1️⃣ Install Python

Download and install Python 3.8 or later from the [official Python website](https://www.python.org/downloads/).

---

### 2️⃣ Install the Required Python Libraries

Install the required dependencies using the following command:

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes essential libraries like:

- **waapi-client**: Communicates with Wwise via WAAPI.
- **customtkinter**
- **Pillow**
---



### 3️⃣ Installing the Command Add-ons (2022.1x+)



1. Navigate to the `%APPDATA%/Audiokinetic/Wwise/Add-ons` directory.If the `Add-ons` folder does not exist, create it.
2. Download this whole repository zip file from GitHub.
3. Unzip the contents of the warpp-audio-waapi-tools folder into the Add-ons directory. ***If you already have an existing Commands folder with a '.json' file for commands, move the '.json' file from this repository into your existing Commands folder to avoid overwriting your current file.***
4. Restart Wwise or use the command Reload Commands (ctrl + shift + k)

---

## 🎓 Additional Resources

- [Learn about WAAPI](https://www.audiokinetic.com/library/edge/?source=SDK&id=waapi.html)
- [Using Python with WAAPI](https://www.audiokinetic.com/library/edge/?source=SDK&id=waapi_client_python_rpc.html)
- [Command Add-ons in Wwise](https://www.audiokinetic.com/library/edge/?source=SDK&id=defining_custom_commands.html)

---

## 📬 Feedback & Contributions

Have suggestions or found a bug? Feel free to open an issue or submit a pull request!

Happy automating! 
