# Grand RP Admin Tracker — Public Website Edition

Deployable FastAPI website for Grand RP forum 36. Date calculations use `Europe/London` (GMT/BST). Admin role tags are used internally and are not shown in tables or CSV reports. Forum URL and scanner limits remain hidden.

## Public deployment (GitHub + Render)

**Do not upload the ZIP as a single file.** Extract the ZIP and upload its contents to the ROOT of a GitHub repository. The root must contain `server.py`, `scanner.py`, `requirements.txt`, `render.yaml` and the `public` folder. Do not upload an extra outer folder.

1. Create a repository at https://github.com/new . Public or private is fine. If you want to keep your project source private, choose *Private* and connect your GitHub account to Render.
2. On GitHub, open the new repo and choose **Add file → Upload files** (if the repo is empty, use **uploading an existing file**). Drag **all the extracted files and the public folder contents** from the extracted ZIP into the browser, and **Commit changes**. Check that `server.py` is visible at the top level of the repo.
3. Sign in to https://dashboard.render.com . Choose **New → Web Service**, connect your GitHub repo and choose the Python runtime.
4. Set **Build Command** to `pip install -r requirements.txt`, **Start Command** to `uvicorn server:app --host 0.0.0.0 --port $PORT` and choose **Free** (if offered). The repository also has an optional `render.yaml` Blueprint configuration if you prefer Render Blueprints.
5. Deploy. When Render reports the app is live, open your provided `https://YOUR-SERVICE.onrender.com` link. Share that exact link with other people.
6. For a health test, visit `https://YOUR-SERVICE.onrender.com/api/health`. It should return JSON containing `"ok": true`. If it fails, inspect the **Logs** section of your Render service.

**Local run (Windows):** In this folder, type `cmd` in the File Explorer address bar and run `py -m pip install -r requirements.txt` then `py -m uvicorn server:app --host 127.0.0.1 --port 8000`. Visit http://127.0.0.1:8000. Keep that terminal open. The ZIP does not contain an executable, and there is no need to disable Smart App Control.

## Important limitations

- A public URL makes the dashboard accessible to others; **it does not guarantee live scanning works**. Grand RP currently blocks some automated requests (for example HTTP 403), and the scanner does not bypass login restrictions or anti-bot checks. If a scan fails, try the **Import CSV** option using data exported from the Chrome extension.
- Scanner results/CSV imports are stored in **each visitor's own browser**. They are **not automatically shared** among visitors. This edition does not include a database or scheduled centralized reporting.
- Because the scanner is triggered by visitors, the public server accepts one scan at a time and other visitors may get a retry error. Hosting may have quotas and slow cold starts, especially on free plans. Free instances are not a dependable production monitoring solution.
- No visitor authentication is included. Anyone with your link may trigger forum requests. For controlled access or shared persistent reports, add authentication, caching, and a database before using it with a large audience.
- Date ranges, summaries, charts and exported timestamps use `Europe/London` and automatically follow GMT/BST changes.
- Counts **unique threads whose CURRENT latest post** is from a tagged admin. They do not reconstruct all historical admin actions. Results may be partial when scans are blocked or interrupted.

## Test

`python -m unittest discover -s test -v`
