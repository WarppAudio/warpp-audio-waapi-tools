🎵 Wwise Python Tools - Simple EXE Setup (WIP)
Welcome to the warpp-audio-waapi-tools repository! This project provides an executable version of Python-based tools that leverage the Wwise Authoring API (WAAPI) to streamline and automate tasks within Audiokinetic Wwise.
🚀 Getting Started
These instructions will guide you through a simplified setup using the executable version of our tools.
🔧 Requirements

Wwise 2022.1.x +
Wwise Authoring API enabled in your Wwise project:

Go to Project > User Preferences and enable Wwise Authoring API



🛠 Simple Installation Steps
1️⃣ Add-ons Directory Setup

If you want the tools to be available in every Wwise installation and project:
- Navigate to the `%APPDATA%/Audiokinetic/Wwise/Add-ons` directory
- If the `Add-ons` folder does not exist, create it
- For other installation methods, watch [this video](https://youtu.be/7LpANxZD1cE?si=pCo8zNlsRYKFv5zi&t=60) or read [this document](https://www.audiokinetic.com/fr/library/edge/?source=SDK&id=defining_custom_commands.html)

2️⃣ File Installation

Copy the event-creation folder to your Add-ons directory
Move the Warpp_waapi_tools.json file to the Commands folder
![image](https://github.com/user-attachments/assets/c9dad62c-2556-486d-bea6-2c88d6f35c3d)

3️⃣ Finishing Up

Restart Wwise or use the command Reload Commands (Ctrl + Shift + K)
No Python installation or additional dependencies required!

🎓 Additional Resources

Learn about WAAPI
Command Add-ons in Wwise

📬 Feedback & Contributions
Have suggestions or found a bug? Feel free to open an issue or submit a pull request!
Happy automating! 🎮 🎵

Note: This version uses a pre-compiled executable, eliminating the need for Python installation and dependency management. Just copy the files and you're ready to go!
