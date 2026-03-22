(function () {
  const form = document.getElementById("local-upload-form");
  const fileInput = document.getElementById("local-file-input");
  const pickFilesBtn = document.getElementById("local-pick-files");
  const pickFolderBtn = document.getElementById("local-pick-folder");
  const fileLabelText = document.getElementById("local-file-label-text");
  const addSuffix = document.getElementById("local-add-suffix");
  const stemField = document.getElementById("local-stem-suffix");
  const chooseDirBtn = document.getElementById("local-choose-dir");
  const dirLabel = document.getElementById("local-dir-label");
  const fsHint = document.getElementById("local-fs-hint");
  const localPreview = document.getElementById("local-preview");
  const localPreviewCount = document.getElementById("local-preview-count");
  const localPreviewGrid = document.getElementById("local-preview-grid");
  const localPreviewNames = document.getElementById("local-preview-names");
  const fsSupported = typeof window.showDirectoryPicker === "function";
  let dirHandle = null;
  /** @type {string[]} */
  let previewObjectUrls = [];
  const MAX_PREVIEW_THUMBS = 48;

  const suffixDefault = () =>
    (window.__LOCAL_SUFFIX__ && String(window.__LOCAL_SUFFIX__).trim()) || "_exif";

  function syncStemField() {
    if (!stemField) return;
    stemField.value = addSuffix && addSuffix.checked ? suffixDefault() : "";
  }

  if (addSuffix) {
    addSuffix.addEventListener("change", syncStemField);
  }
  syncStemField();

  if (fsHint) {
    fsHint.hidden = fsSupported;
  }

  function clearLocalPreview() {
    previewObjectUrls.forEach((u) => URL.revokeObjectURL(u));
    previewObjectUrls = [];
    if (localPreviewGrid) localPreviewGrid.innerHTML = "";
    if (localPreviewNames) localPreviewNames.innerHTML = "";
    if (localPreviewCount) localPreviewCount.textContent = "";
    if (localPreview) localPreview.hidden = true;
  }

  function updateLocalPreview() {
    clearLocalPreview();
    if (!fileInput || !localPreview) return;
    const files = fileInput.files;
    if (!files || !files.length) {
      localPreview.hidden = true;
      return;
    }
    localPreview.hidden = false;
    const n = files.length;
    let imageCount = 0;
    for (let i = 0; i < files.length; i++) {
      if (files[i].type.startsWith("image/")) imageCount += 1;
    }
    if (localPreviewCount) {
      let line = `${n} file(s) selected`;
      if (imageCount !== n) line += ` (${imageCount} image preview)`;
      if (n > MAX_PREVIEW_THUMBS) {
        line += ` — showing ${MAX_PREVIEW_THUMBS} thumbnails`;
      }
      localPreviewCount.textContent = line;
    }
    if (localPreviewNames) {
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        const rel = f.webkitRelativePath || f.name;
        const li = document.createElement("li");
        li.textContent = rel;
        localPreviewNames.appendChild(li);
      }
    }
    if (localPreviewGrid) {
      let shown = 0;
      for (let i = 0; i < files.length && shown < MAX_PREVIEW_THUMBS; i++) {
        const f = files[i];
        if (!f.type.startsWith("image/")) continue;
        const url = URL.createObjectURL(f);
        previewObjectUrls.push(url);
        const rel = f.webkitRelativePath || f.name;
        const img = document.createElement("img");
        img.src = url;
        img.alt = rel;
        img.loading = "lazy";
        img.decoding = "async";
        localPreviewGrid.appendChild(img);
        shown += 1;
      }
    }
  }

  function setPickMode(mode) {
    if (!fileInput) return;
    fileInput.value = "";
    if (mode === "folder") {
      fileInput.setAttribute("webkitdirectory", "");
      fileInput.setAttribute("multiple", "");
    } else {
      fileInput.removeAttribute("webkitdirectory");
      fileInput.setAttribute("multiple", "");
    }
    if (pickFilesBtn) {
      pickFilesBtn.classList.toggle("is-active", mode === "files");
      pickFilesBtn.setAttribute("aria-pressed", mode === "files" ? "true" : "false");
    }
    if (pickFolderBtn) {
      pickFolderBtn.classList.toggle("is-active", mode === "folder");
      pickFolderBtn.setAttribute("aria-pressed", mode === "folder" ? "true" : "false");
    }
    const labelStr = mode === "folder" ? "Choose folder" : "Choose files";
    if (fileLabelText) {
      fileLabelText.textContent = labelStr;
    }
    fileInput.setAttribute("aria-label", labelStr);
    clearLocalPreview();
  }

  if (pickFilesBtn && pickFolderBtn && fileInput) {
    pickFilesBtn.addEventListener("click", () => setPickMode("files"));
    pickFolderBtn.addEventListener("click", () => setPickMode("folder"));
    setPickMode("files");
  }

  if (chooseDirBtn) {
    chooseDirBtn.style.display = fsSupported ? "inline-flex" : "none";
    chooseDirBtn.addEventListener("click", async () => {
      if (!fsSupported) return;
      try {
        dirHandle = await window.showDirectoryPicker();
        if (dirLabel) {
          dirLabel.hidden = false;
          dirLabel.textContent = "Output folder selected";
        }
      } catch (e) {
        if (e.name !== "AbortError") console.error(e);
      }
    });
  }

  if (!form || !fileInput) return;

  fileInput.addEventListener("change", updateLocalPreview);

  /** Full page POST so the browser follows Flask’s 302 (fetch + manual redirect often hides Location). */
  function submitWithRelativePaths() {
    form.querySelectorAll('input[name="relative_paths"][data-local-rel="1"]').forEach((el) => {
      el.remove();
    });
    const files = fileInput.files;
    if (!files?.length) return;
    for (let i = 0; i < files.length; i++) {
      const inp = document.createElement("input");
      inp.type = "hidden";
      inp.name = "relative_paths";
      inp.value = files[i].webkitRelativePath || files[i].name;
      inp.setAttribute("data-local-rel", "1");
      form.appendChild(inp);
    }
    form.submit();
  }

  async function writeFileRecursive(dir, relativePath, blob) {
    const parts = relativePath.split("/").filter(Boolean);
    for (const p of parts) {
      if (p === ".." || p === ".") throw new Error("Invalid path");
    }
    let handle = dir;
    for (let i = 0; i < parts.length - 1; i++) {
      handle = await handle.getDirectoryHandle(parts[i], { create: true });
    }
    const fileH = await handle.getFileHandle(parts[parts.length - 1], {
      create: true,
    });
    const writable = await fileH.createWritable();
    await writable.write(blob);
    await writable.close();
  }

  form.addEventListener("submit", async (e) => {
    syncStemField();
    const files = fileInput.files;
    if (!files || !files.length) return;

    e.preventDefault();
    const fd = new FormData();
    for (let i = 0; i < files.length; i++) {
      fd.append("file", files[i]);
      fd.append(
        "relative_paths",
        files[i].webkitRelativePath || files[i].name
      );
    }
    fd.append("stem_suffix", stemField ? stemField.value : "");

    if (fsSupported && dirHandle) {
      try {
        const res = await fetch(form.action, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: fd,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          alert(
            data.detail ||
              (data.errors && data.errors.join("\n")) ||
              "Something went wrong."
          );
          return;
        }
        for (const f of data.files || []) {
          const imgBlob = await fetch(f.image_url).then((r) => r.blob());
          await writeFileRecursive(dirHandle, f.relative_path, imgBlob);
          if (f.json_url && f.json_relative_path) {
            const jBlob = await fetch(f.json_url).then((r) => r.blob());
            await writeFileRecursive(dirHandle, f.json_relative_path, jBlob);
          }
        }
        let msg = `Saved ${data.processed} image(s) and JSON sidecars to your folder.`;
        if (data.errors && data.errors.length) {
          msg += "\n\nSome files had errors:\n" + data.errors.join("\n");
        }
        alert(msg);
      } catch (err) {
        console.error(err);
        alert("Failed to save files to your folder.");
      }
      return;
    }

    if (fsSupported && !dirHandle) {
      const go = confirm(
        "No output folder chosen. Process on the server and open the download page instead?"
      );
      if (!go) return;
    }

    submitWithRelativePaths();
  });
})();
