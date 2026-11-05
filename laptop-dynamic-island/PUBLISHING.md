# Publishing & auto-updates

Goal: share the app once, then push updates **without anyone re-downloading a folder.**

The app already has a self-updater built in (`updater.py`). On launch it reads a
small `latest.json` you host online; if the `version` there is newer than the
running one, it downloads the new zip, swaps the files in (keeping each user's
`config.json` and `notes.txt`), and relaunches. You just publish a new release.

## One-time setup (GitHub — free)

1. Create a free account at github.com and make a new **public** repository,
   e.g. `laptop-dynamic-island`.
2. Upload these source files to it (drag-and-drop in the browser is fine).
3. Add a file called **`latest.json`** at the repo root (copy
   `latest.json.example`, fill in your username/repo):
   ```json
   { "version": "2.3.0",
     "zip_url": "https://github.com/YOUR_USERNAME/laptop-dynamic-island/releases/latest/download/laptop-dynamic-island.zip" }
   ```
4. Create a **Release**: Releases → "Draft a new release" → tag `v2.3.0` →
   attach a zip of the app named exactly `laptop-dynamic-island.zip` → Publish.
5. In each user's `config.json`, set the update URL to the **raw** latest.json:
   ```json
   "update": { "auto": true,
     "url": "https://raw.githubusercontent.com/YOUR_USERNAME/laptop-dynamic-island/main/latest.json" }
   ```
   (Ship your build with this already filled in, so users never touch it.)

## Pushing an update later

1. Change the code, bump `VERSION` in `island.py` (e.g. `2.4.0`).
2. Zip the folder as `laptop-dynamic-island.zip`.
3. Publish a new GitHub Release with tag `v2.4.0` and that zip attached.
4. Update `version` in `latest.json` to `2.4.0`.

Next time anyone's island starts, it updates itself to 2.4.0. Done.

> Tip: I can set this GitHub repo + release up with you step by step — just say so.
