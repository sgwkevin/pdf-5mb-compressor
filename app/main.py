import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TARGET_MB = float(os.getenv("TARGET_MB", "5"))
TARGET_BYTES = int(TARGET_MB * 1024 * 1024)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "120"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

app = FastAPI(title="PDF 5MB Compressor")


STRATEGIES = [
    {
        "name": "清晰",
        "pdfsettings": "/ebook",
        "resolution": 150,
        "jpegq": 85,
    },
    {
        "name": "标准",
        "pdfsettings": "/screen",
        "resolution": 120,
        "jpegq": 75,
    },
    {
        "name": "强压缩",
        "pdfsettings": "/screen",
        "resolution": 96,
        "jpegq": 65,
    },
    {
        "name": "极限压缩",
        "pdfsettings": "/screen",
        "resolution": 72,
        "jpegq": 50,
    },
]


def safe_filename(name: str) -> str:
    base = Path(name or "uploaded.pdf").stem.strip() or "uploaded"
    keep = []
    for ch in base:
        if ch.isalnum() or ch in ("-", "_", " ", ".", "（", "）", "(", ")"):
            keep.append(ch)
    cleaned = "".join(keep).strip() or "compressed"
    return cleaned[:80]


def run_ghostscript(src: Path, dst: Path, strategy: dict) -> None:
    res = strategy["resolution"]
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={strategy['pdfsettings']}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",
        f"-dColorImageResolution={res}",
        f"-dGrayImageResolution={res}",
        f"-dMonoImageResolution={max(res * 2, 150)}",
        f"-dJPEGQ={strategy['jpegq']}",
        f"-sOutputFile={dst}",
        str(src),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def compress_pdf(src: Path, workdir: Path) -> tuple[Path, dict]:
    original_size = src.stat().st_size
    if original_size <= TARGET_BYTES:
        copied = workdir / f"already-under-{uuid.uuid4().hex}.pdf"
        shutil.copy2(src, copied)
        return copied, {
            "strategy": "无需压缩",
            "original_size": original_size,
            "output_size": copied.stat().st_size,
        }

    best_path = None
    best_meta = None

    for strategy in STRATEGIES:
        out = workdir / f"compressed-{strategy['name']}-{uuid.uuid4().hex}.pdf"
        try:
            run_ghostscript(src, out, strategy)
        except (subprocess.CalledProcessError, FileNotFoundError):
            if out.exists():
                out.unlink(missing_ok=True)
            continue

        if not out.exists() or out.stat().st_size == 0:
            continue

        size = out.stat().st_size
        if best_meta is None or size < best_meta["output_size"]:
            best_path = out
            best_meta = {
                "strategy": strategy["name"],
                "original_size": original_size,
                "output_size": size,
                "resolution": strategy["resolution"],
                "jpegq": strategy["jpegq"],
            }

        if size <= TARGET_BYTES:
            return out, best_meta

    if not best_path or not best_meta:
        raise HTTPException(status_code=500, detail="压缩失败：服务器没有可用的 PDF 压缩能力，请确认 Ghostscript 已安装。")

    raise HTTPException(
        status_code=422,
        detail=(
            f"已尝试极限压缩，但仍为 {best_meta['output_size'] / 1024 / 1024:.2f}MB，"
            f"无法保证压到 {TARGET_MB:g}MB 以内。建议拆分 PDF 或降低图片清晰度。"
        ),
    )


def cleanup_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


@app.post("/api/compress")
async def compress(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件。")

    workdir = Path(tempfile.mkdtemp(prefix="pdf-compress-"))
    background_tasks.add_task(cleanup_dir, str(workdir))

    src = workdir / "input.pdf"
    total = 0
    with src.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"文件太大，当前上限为 {MAX_UPLOAD_MB}MB。")
            f.write(chunk)

    out, meta = compress_pdf(src, workdir)
    download_name = f"{safe_filename(file.filename)}_compressed_under_{TARGET_MB:g}MB.pdf"

    headers = {
        "X-Original-Size-MB": f"{meta['original_size'] / 1024 / 1024:.2f}",
        "X-Output-Size-MB": f"{meta['output_size'] / 1024 / 1024:.2f}",
        "X-Compress-Strategy": meta["strategy"],
    }
    return FileResponse(
        out,
        media_type="application/pdf",
        filename=download_name,
        headers=headers,
        background=background_tasks,
    )


@app.get("/api/health")
def health():
    return {"ok": True, "target_mb": TARGET_MB, "max_upload_mb": MAX_UPLOAD_MB}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

