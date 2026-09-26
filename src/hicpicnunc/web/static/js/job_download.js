(function () {
  const btn = document.getElementById("job-save-all");
  const manifestEl = document.getElementById("job-download-manifest");
  if (!btn || !manifestEl) return;

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

  btn.addEventListener("click", async () => {
    let manifest;
    try {
      manifest = JSON.parse(manifestEl.textContent);
    } catch (e) {
      alert("Could not read the file list.");
      return;
    }
    if (!manifest.length) return;

    let dirHandle;
    try {
      dirHandle = await window.showDirectoryPicker();
    } catch (e) {
      if (e.name === "AbortError") return;
      return;
    }

    try {
      for (const item of manifest) {
        const url = item.url.startsWith("http")
          ? item.url
          : new URL(item.url, window.location.origin).href;
        const res = await fetch(url, { credentials: "same-origin" });
        if (!res.ok) {
          throw new Error(item.path + ": HTTP " + res.status);
        }
        const blob = await res.blob();
        await writeFileRecursive(dirHandle, item.path, blob);
      }
      alert("Saved " + manifest.length + " file(s) to your folder.");
    } catch (err) {
      console.error(err);
      alert("Could not save all files. " + (err.message || String(err)));
    }
  });
})();
