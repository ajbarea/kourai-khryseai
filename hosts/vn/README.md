# Kourai Khryseai: VN Host (Visual Novel GUI)

The **VN Host** is an alternative user interface for interacting with the Kourai Khryseai agent system. Built on the [Ren'Py Visual Novel Engine](https://www.renpy.org/), it focuses on character-driven storytelling, immersive visuals, and relationship-building with the Golden Maidens.

---

## 🛠️ Prerequisites

To develop or run the VN Host, you must have the Ren'Py SDK installed locally in this directory.

1.  **Download:** [Ren'Py 8.5.2 SDK](https://www.renpy.org/latest.html) (Windows/Linux/macOS).
2.  **Install:** Unzip the SDK contents into `hosts/vn/renpy-8.5.2-sdk/`.
3.  **Verification:** Ensure `hosts/vn/renpy-8.5.2-sdk/renpy.exe` (on Windows) or `renpy.sh` (on Linux/macOS) exists.

> **Note:** The SDK folder is ignored by git to prevent repository bloat.

---

## 🚀 Getting Started

### 1. Launching the SDK
Run the Ren'Py Launcher to manage projects:
```powershell
# Windows
.\hosts\vn\renpy-8.5.2-sdk\renpy.exe
```

### 2. Running the VN Project
If you have a project directory (e.g., `hosts/vn/kourai_vn/`), you can launch it directly:
```powershell
.\hosts\vn\renpy-8.5.2-sdk\renpy.exe .\hosts\vn\kourai_vn\
```

---

## 🏗️ Project Structure

The VN Host follows the standard Ren'Py project layout within a subdirectory of `hosts/vn/`:

```text
hosts/vn/kourai_vn/
├── game/                   # Main source code
│   ├── script.rpy          # Main narrative logic & bridge init
│   ├── screens.rpy         # UI/HUD definitions
│   ├── options.rpy         # Window & build configuration
│   ├── gui.rpy             # Global GUI styling
│   ├── bridge.py           # Subprocess IPC bridge to agents
│   └── images/             # Maidens (Golden Avatars) and backgrounds
└── ...
```

---

## 🌉 Agent Integration (Bridge)

The VN Host communicates with the `@agents/**` backend via a **JSON-over-Subprocess** bridge. This allows the VN to:
- Route player input to **Hephaestus** (Orchestrator).
- Display real-time status updates from **Metis**, **Techne**, etc.
- Reflect agent state through portraits and transitions.
- Track player-agent relationship metrics (Affinity/Tiers).

---

## ⌨️ Development Tips

- **Live Reload:** Press `Shift + R` while the game is running to instantly reload script changes.
- **Linting:** Check for syntax errors using the launcher or CLI:
  ```powershell
  .\hosts\vn\renpy-8.5.2-sdk\renpy.exe .\hosts\vn\kourai_vn\ lint
  ```
- **Console:** Press `Shift + O` in-game to open the Ren'Py/Python console for debugging.
- **Trace Logs:** Agent communication logs are written to `logs/bridge_renpy.log`.

---

## 📜 License
This host is part of the Kourai Khryseai project. See [LICENSE.md](../../LICENSE.md) for details.
