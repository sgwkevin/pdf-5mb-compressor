const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#fileInput");
const pickBtn = document.querySelector("#pickBtn");
const statusText = document.querySelector(".statusText");
const bar = document.querySelector(".bar");
const result = document.querySelector("#result");
const resultText = document.querySelector("#resultText");
const downloadLink = document.querySelector("#downloadLink");
const errorBox = document.querySelector("#error");

function setStatus(text, active = false) {
  statusText.textContent = text;
  bar.classList.toggle("active", active);
  if (!active) {
    bar.querySelector("span").style.width = text === "压缩完成" ? "100%" : "0";
  }
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  result.classList.add("hidden");
  setStatus("处理失败", false);
}

function resetMessages() {
  errorBox.classList.add("hidden");
  result.classList.add("hidden");
  if (downloadLink.href) URL.revokeObjectURL(downloadLink.href);
}

async function upload(file) {
  resetMessages();

  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    showError("请上传 PDF 文件。");
    return;
  }

  const data = new FormData();
  data.append("file", file);

  setStatus(`正在上传并压缩：${file.name}`, true);

  try {
    const response = await fetch("/api/compress", {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      let message = "压缩失败，请换一个文件试试。";
      try {
        const payload = await response.json();
        message = payload.detail || message;
      } catch {
        message = await response.text();
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const original = response.headers.get("X-Original-Size-MB");
    const output = response.headers.get("X-Output-Size-MB");
    const strategy = response.headers.get("X-Compress-Strategy");

    downloadLink.href = url;
    downloadLink.download = file.name.replace(/\.pdf$/i, "") + "_compressed.pdf";
    resultText.textContent = `原文件 ${original || "-"}MB，压缩后 ${output || "-"}MB，使用策略：${strategy || "-"}。`;
    result.classList.remove("hidden");
    setStatus("压缩完成", false);
  } catch (err) {
    showError(err.message);
  }
}

pickBtn.addEventListener("click", () => fileInput.click());
form.addEventListener("click", (event) => {
  if (event.target === form) fileInput.click();
});

fileInput.addEventListener("change", () => upload(fileInput.files[0]));

["dragenter", "dragover"].forEach((name) => {
  form.addEventListener(name, (event) => {
    event.preventDefault();
    form.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((name) => {
  form.addEventListener(name, (event) => {
    event.preventDefault();
    form.classList.remove("dragging");
  });
});

form.addEventListener("drop", (event) => {
  upload(event.dataTransfer.files[0]);
});
