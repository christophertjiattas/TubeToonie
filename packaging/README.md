# Packaging TubeToonie (double-click app icon)

## macOS: Create a `.app` you can pin to the Dock

TubeToonie is a local Streamlit server. A macOS app wrapper can launch it for you.

### Option 1 (free): Automator
1. Open **Automator**
2. Create a new **Application**
3. Add action: **Run Shell Script**
4. Paste this (update the path to your repo):

```bash
cd "/path/to/TubeToonie"
chmod +x run-ui-easy.sh
./run-ui-easy.sh
```

5. Save as `TubeToonie.app`
6. Double-click it. (First run may require right-click -> Open.)

### Option 2 (nicer): Platypus
Platypus builds a proper macOS `.app` wrapper.
- https://sveinbjorn.org/platypus

Use it to run a script like:
```bash
cd "/path/to/TubeToonie"
./run-ui-easy.sh
```

## Windows: Shortcut
The simplest approach is to use `launchers/TubeToonie.bat` and create a desktop shortcut to it.

## Notes / gotchas
- Streamlit opens a local server. Closing the browser tab doesn’t stop the server.
- To stop it, close the Terminal window or press **Ctrl+C** in the console.
- Fully standalone packaging (bundling Python + deps) is possible but heavier and more brittle with Streamlit + ffmpeg + keyring.
