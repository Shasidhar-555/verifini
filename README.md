# VerifINI

A small hackathon prototype for checking image/caption context **before publishing**. The UI uses a restrained navy, off-white, and muted teal palette; no neon or glowing effects.

## What works

- Upload an image and enter a caption and description.
- Compare the image against images in the local evidence index using a 64-bit difference hash.
- Compare text against indexed claims with character n-gram TF-IDF.
- Detect a small set of time/date/location phrases.
- Show a cautious result, reasons, evidence records, and a template-based suggested caption.
- Edit, publish, and view posts in a local demo feed.
- Record a simple challenge/feedback entry.

## Important limitations

- This is a prototype, **not a whole-internet fact checker**. It checks only records in `data/evidence.json` and images in `data/images/`.
- All included evidence is clearly marked as sample data. The included flood image is a synthetic illustration, not a real news photograph.
- A perceptual-hash match means visual similarity, not proof of reuse, falsehood, date, or location.
- Text flags are simple rules, and TF-IDF similarity is not fact verification.
- Do not use demo source links as real evidence. Add a real source only after verifying the record and link.
- Uploaded post images are stored as data URLs in the local `posts.json` file when published. This is for a small local demo only, not production use.

## Run in VS Code

1. Open this `verifini` folder in VS Code.
2. Open **Terminal → New Terminal**.
3. Create and activate a virtual environment:

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Start the app:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
6. Open <http://127.0.0.1:8000> in your browser.

If PowerShell blocks virtual-environment activation, run `\.venv\Scripts\python.exe -m pip install -r requirements.txt` and then `\.venv\Scripts\python.exe -m uvicorn app.main:app --reload` without activating it.

## Quick demo

- Use `data/images/sample_flood_illustration.png` as the uploaded image.
- Caption: `Massive flooding in Chennai right now! Stay safe.`
- Click **Check Before Posting**. Since the image matches the local sample image record and the caption says `right now`, the result should be **Possible misleading context**.
- Try a neutral caption like `Illustration for a post about flood preparedness` to see **Related content found**.
- Try a new photo with no match to see an inconclusive result.

## Add an evidence record

Add an image file to `data/images/`, then add a record to `data/evidence.json` with the following fields:

```json
{
  "id": "REC-004",
  "is_sample": true,
  "image_file": "your_image.jpg",
  "claim_text": "A short description of the record",
  "description": "Context for this record",
  "location": "Recorded location or Not established",
  "recorded_date": "2024-05-01",
  "source_name": "Sample record",
  "source_url": "",
  "credibility_label": "Sample only"
}
```

Use real-world sources only when you have verified them and have permission to use the image/data. Restart the app after changing the evidence index if needed.

## Project structure

```text
verifini/
├── app/
│   └── main.py
├── data/
│   ├── evidence.json
│   ├── posts.json
│   ├── challenges.json
│   └── images/
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt
└── README.md
```
