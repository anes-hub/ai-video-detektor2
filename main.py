
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import torch

from PIL import Image
from fastapi.middleware.cors import CORSMiddleware, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from transformers import (
    VideoMAEForVideoClassification,
    VideoMAEImageProcessor,
)


# POSTAVKE
MODEL_ID = "Vansh180/VideoMae-ffc23-deepfake-detector"

MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_DURATION = 180
NUM_FRAMES = 16

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


# FASTAPI
app = FastAPI(title="DeepFake AI Detector")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Za lokalni razvoj
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# UČITAVANJE MODELA
_model = None
_processor = None
_device = None


def load_model():
    global _model, _processor, _device

    if _model is not None:
        return _model, _processor, _device

    _device = (
        "mps"
        if torch.backends.mps.is_available()
        else "cpu"
    )

    _processor = VideoMAEImageProcessor.from_pretrained(
        MODEL_ID
    )

    try:
        _model = (
            VideoMAEForVideoClassification
            .from_pretrained(MODEL_ID)
            .to(_device)
        )

    except Exception:
        _device = "cpu"

        _model = (
            VideoMAEForVideoClassification
            .from_pretrained(MODEL_ID)
            .to(_device)
        )

    _model.eval()

    return _model, _processor, _device


# IZDVAJANJE SLIČICA
def extract_frames(video_path):
    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        raise ValueError("Video se ne može otvoriti.")

    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        total_frames = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        width = int(
            capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        )

        height = int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )

        if fps <= 0 or total_frames <= 0:
            raise ValueError("Video nema validne sličice.")

        duration = total_frames / fps

        if duration > MAX_DURATION:
            raise ValueError("Video je duži od 180 sekundi.")

        if max(width, height) > 3840:
            raise ValueError("Video ima rezoluciju veću od 4K.")

        indices = np.linspace(
            0,
            total_frames - 1,
            min(NUM_FRAMES, total_frames),
            dtype=int,
        )

        frames = []

        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            success, frame = capture.read()

            if success:
                frame_rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB,
                )
                frames.append(Image.fromarray(frame_rgb))

        if not frames:
            raise ValueError("Nije moguće izdvojiti sličice.")

        return frames, duration, width, height

    finally:
        capture.release()


# AI ANALIZA
def analyze_video(model, processor, frames, device):
    required_frames = getattr(
        model.config,
        "num_frames",
        NUM_FRAMES,
    )

    indices = np.linspace(
        0,
        len(frames) - 1,
        min(required_frames, len(frames)),
        dtype=int,
    )

    selected_frames = [
        frames[i].convert("RGB")
        for i in indices
    ]

    while len(selected_frames) < required_frames:
        selected_frames.append(selected_frames[-1])

    inputs = processor(
        images=selected_frames,
        return_tensors="pt",
    )

    pixel_values = inputs["pixel_values"]

    if pixel_values.ndim == 4:
        pixel_values = pixel_values.unsqueeze(0)

    if pixel_values.ndim != 5:
        raise ValueError("Neispravan format podataka modela.")

    if pixel_values.shape[1] != required_frames:
        raise ValueError("Neispravan broj sličica.")

    pixel_values = pixel_values.to(device)

    with torch.inference_mode():
        output = model(pixel_values=pixel_values)

        probabilities = torch.softmax(
            output.logits,
            dim=-1,
        )[0]

    labels = model.config.id2label
    results = []

    for index, probability in enumerate(
        probabilities.tolist()
    ):
        label = labels.get(
            index,
            labels.get(str(index), str(index)),
        )

        results.append({
            "label": str(label),
            "score": float(probability),
        })

    return results


# PRONALAŽENJE FAKE KLASE
def find_fake_label(results):
    fake_words = (
        "fake",
        "deepfake",
        "manipulated",
        "synthetic",
        "generated",
        "forged",
    )

    for result in results:
        label = (
            result["label"]
            .lower()
            .replace("_", " ")
            .replace("-", " ")
        )

        if any(word in label for word in fake_words):
            return result

    return None


# API ENDPOINT
@app.get("/")
def home():
    return {
        "status": "online",
        "message": "DeepFake AI Detector backend is running."
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Nepodržan format videa."
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temp_file:

            temp_path = temp_file.name
            total_size = 0

            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Video je veći od 100 MB."
                    )

                temp_file.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Datoteka je prazna."
            )

        frames, duration, width, height = (
            await run_in_threadpool(
                extract_frames,
                temp_path,
            )
        )

        model, processor, device = await run_in_threadpool(
            load_model
        )

        results = await run_in_threadpool(
            analyze_video,
            model,
            processor,
            frames,
            device,
        )

        fake_result = find_fake_label(results)

        return {
            "success": True,
            "filename": file.filename,
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "analyzed_frames": len(frames),
            "device": device,
            "fake_result": fake_result,
            "results": results,
            "message": (
                "Model je završio analizu. "
                "Rezultat nije konačan dokaz o porijeklu videa."
            )
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print("ANALYSIS ERROR:", repr(error))

        raise HTTPException(
            status_code=500,
            detail="Došlo je do greške tokom AI analize."
        )

    finally:
        await file.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
