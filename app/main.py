from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IMAGE_DIR = DATA_DIR / "images"
STATIC_DIR = ROOT / "static"
EVIDENCE_PATH = DATA_DIR / "evidence.json"
POSTS_PATH = DATA_DIR / "posts.json"
CHALLENGES_PATH = DATA_DIR / "challenges.json"

app = FastAPI(title="VerifINI", description="A prototype for pre-publishing context checks.")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/sample-images", StaticFiles(directory=IMAGE_DIR), name="sample-images")

TIME_TERMS = [
    "today", "right now", "currently", "breaking", "just now", "live", "this morning",
    "இன்று", "இப்போது", "நேரலை", "இப்போதுதான்", "आज", "अभी", "ताज़ा खबर", "लाइव",
]
LOCATION_TERMS = ["in chennai", "at chennai", "சென்னையில்", "சென்னை", "चेन्नई में"]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        path.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_evidence() -> list[dict[str, Any]]:
    return read_json(EVIDENCE_PATH, [])


def dhash(image: Image.Image) -> int:
    """Return a 64-bit difference hash using only Pillow."""
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            left = pixels[y * 9 + x]
            right = pixels[y * 9 + x + 1]
            bits = (bits << 1) | int(left > right)
    return bits


def safe_image_hash(image_bytes: bytes):
    try:
        import io
        with Image.open(io.BytesIO(image_bytes)) as im:
            im.verify()
        with Image.open(io.BytesIO(image_bytes)) as im:
            return dhash(im)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="That file doesn\'t appear to be a supported image. Try PNG, JPG, or WEBP.")


def record_hashes(record: dict[str, Any]):
    filename = record.get("image_file")
    if not filename:
        return None
    path = (IMAGE_DIR / filename).resolve()
    if IMAGE_DIR.resolve() not in path.parents or not path.exists():
        return None
    try:
        with Image.open(path) as im:
            return dhash(im)
    except (OSError, ValueError):
        return None


def find_image_matches(image_bytes: bytes | None, records: list[dict[str, Any]]):
    if not image_bytes:
        return []
    uploaded_hash = safe_image_hash(image_bytes)
    found = []
    for record in records:
        record_hash = record_hashes(record)
        if record_hash is None:
            continue
        distance = (uploaded_hash ^ record_hash).bit_count()
        # dHash is a 64-bit hash. Lower distance means more visually similar.
        if distance <= 18:
            found.append({**record, "hash_distance": int(distance), "similarity": round(max(0, 1 - distance / 64), 2)})
    return sorted(found, key=lambda x: x["hash_distance"])


def find_text_matches(text: str, records: list[dict[str, Any]]):
    text = text.strip()
    if not text or not records:
        return []
    corpus = [f"{r.get('claim_text', '')} {r.get('description', '')}" for r in records]
    try:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        matrix = vectorizer.fit_transform(corpus + [text])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    except ValueError:
        return []
    matches = []
    for i, score in enumerate(scores):
        if score >= 0.18:
            matches.append({**records[i], "text_similarity": round(float(score), 2)})
    return sorted(matches, key=lambda x: x["text_similarity"], reverse=True)[:3]


def extract_flags(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    flags = []
    for term in TIME_TERMS:
        if term.lower() in lowered:
            flags.append({"type": "time_claim", "text": term})
    for term in LOCATION_TERMS:
        if term.lower() in lowered:
            flags.append({"type": "location_claim", "text": term})
    date_patterns = [r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\b20\d{2}\b"]
    for pattern in date_patterns:
        for match in re.findall(pattern, text):
            flags.append({"type": "date_claim", "text": match})
    # Keep results compact and avoid repeated terms.
    unique = []
    seen = set()
    for flag in flags:
        key = (flag["type"], flag["text"].lower())
        if key not in seen:
            unique.append(flag)
            seen.add(key)
    return unique


def analyze_content(image_bytes: bytes | None, caption: str, description: str):
    records = get_evidence()
    combined_text = f"{caption}\n{description}".strip()
    flags = extract_flags(combined_text)
    image_matches = find_image_matches(image_bytes, records)
    text_matches = find_text_matches(combined_text, records)
    evidence_by_id = {}
    for item in image_matches + text_matches:
        evidence_by_id[item["id"]] = item
    evidence = list(evidence_by_id.values())[:4]
    current_claim = any(flag["type"] == "time_claim" for flag in flags)
    today = date.today()
    old_match = False
    for item in image_matches:
        try:
            record_date = date.fromisoformat(item.get("recorded_date", "1900-01-01"))
            if (today - record_date).days > 7:
                old_match = True
        except (TypeError, ValueError):
            continue
    location_claim = any(flag["type"] == "location_claim" for flag in flags)
    matched_location = next((m.get("location") for m in image_matches if m.get("location")), None)
    location_mismatch = bool(location_claim and matched_location and "chennai" not in combined_text.lower() and "சென்னை" not in combined_text)

    if image_matches and ((current_claim and old_match) or location_mismatch):
        verdict = "Possible misleading context"
        confidence = "Medium"
        summary = "A similar image appears in an earlier record, while the caption or description suggests a current or different context. Review the evidence before sharing."
        reasons = [f"Visually similar to record {image_matches[0]['id']} (hash distance {image_matches[0]['hash_distance']}/64)."]
        if current_claim and old_match:
            reasons.append(f"The matched record is dated {image_matches[0].get('recorded_date', 'unknown date')}, and the text includes a current-time phrase.")
        if location_mismatch:
            reasons.append("The stated location may not align with the matched record; confirm it manually.")
    elif image_matches:
        verdict = "Related content found"
        confidence = "Medium"
        summary = "A visually similar image exists in the evidence index. Similarity alone does not establish whether the post is accurate or misleading."
        reasons = [f"Closest visual match: {image_matches[0]['id']} (hash distance {image_matches[0]['hash_distance']}/64)."]
    elif flags or text_matches:
        verdict = "Needs verification"
        confidence = "Low"
        summary = "The text contains time, date, or location wording, or resembles an indexed claim, but the available records are not enough to confirm it."
        reasons = [f"Detected wording that may need checking: {', '.join(f['text'] for f in flags[:5])}."] if flags else ["Related text was found, but no strong image match was available."]
    else:
        verdict = "No match found in available records"
        confidence = "Low"
        summary = "No sufficiently similar item was found in this prototype's evidence index. This does not prove that the post is authentic."
        reasons = ["No matching record crossed the prototype's similarity threshold."]

    # Only link to records that actually exist in the local index.
    public_evidence = []
    for item in evidence:
        public_evidence.append({
            "id": item.get("id"),
            "is_sample": bool(item.get("is_sample", True)),
            "image_url": f"/sample-images/{item['image_file']}" if item.get("image_file") and (IMAGE_DIR / item['image_file']).exists() else None,
            "claim_text": item.get("claim_text", ""),
            "location": item.get("location", "Not recorded"),
            "recorded_date": item.get("recorded_date", "Not recorded"),
            "source_name": item.get("source_name", "Source not recorded"),
            "source_url": item.get("source_url", ""),
            "credibility_label": item.get("credibility_label", "Not assessed"),
            "similarity": item.get("similarity", item.get("text_similarity")),
            "match_type": "image" if item.get("hash_distance") is not None else "text",
            "hash_distance": item.get("hash_distance"),
        })

    suggested_caption = caption.strip()
    if verdict == "Possible misleading context" and caption.strip():
        suggested_caption = f"Context and date need verification: {caption.strip()}"
    elif verdict == "Needs verification" and caption.strip():
        suggested_caption = f"Unverified report: {caption.strip()}"

    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "reasons": reasons,
        "evidence": public_evidence,
        "flags": flags,
        "suggested_caption": suggested_caption,
        "disclaimer": "This prototype checks a local evidence index only. No match does not mean authentic; a match does not prove misuse or falsity.",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "evidence_records": len(get_evidence())}


@app.post("/analyze")
async def analyze(
    caption: str = Form(""),
    description: str = Form(""),
    image: UploadFile | None = File(None),
):
    if not caption.strip() and not description.strip() and image is None:
        raise HTTPException(status_code=400, detail="Add an image, caption, or description before checking.")
    image_bytes = None
    if image is not None and image.filename:
        if image.content_type and not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Please upload an image file.")
        image_bytes = await image.read()
        if len(image_bytes) > 8 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image is too large. Use an image smaller than 8 MB.")
    return analyze_content(image_bytes, caption, description)


@app.post("/publish")
def publish(payload: dict[str, Any]):
    caption = str(payload.get("caption", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not caption and not description and not payload.get("image_url"):
        raise HTTPException(status_code=400, detail="Add some post content before publishing.")
    posts = read_json(POSTS_PATH, [])
    post = {
        "id": f"POST-{int(datetime.now().timestamp())}",
        "caption": caption,
        "description": description,
        "image_url": payload.get("image_url"),
        "analysis": payload.get("analysis", {}),
        "published_at": datetime.now().isoformat(timespec="seconds"),
    }
    posts.insert(0, post)
    write_json(POSTS_PATH, posts[:100])
    return {"ok": True, "post": post}


@app.get("/feed")
def feed():
    return read_json(POSTS_PATH, [])


@app.post("/challenge")
def challenge(payload: dict[str, Any]):
    items = read_json(CHALLENGES_PATH, [])
    entry = {
        "post_id": str(payload.get("post_id", "unknown")),
        "feedback": str(payload.get("feedback", "User requested a review"))[:500],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    items.append(entry)
    write_json(CHALLENGES_PATH, items)
    return {"ok": True, "message": "Feedback recorded for this prototype."}
