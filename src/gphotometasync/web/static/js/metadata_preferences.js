(function () {
  const cameraDetails = document.getElementById("metadata-camera-details");
  const gpsLocation = document.getElementById("metadata-gps-location");
  const includeJson = document.getElementById("metadata-include-json");
  const saveButton = document.getElementById("metadata-save-preferences");
  const resetButton = document.getElementById("metadata-reset-defaults");
  const status = document.getElementById("metadata-preferences-status");

  if (!cameraDetails || !gpsLocation || !includeJson || !saveButton || !resetButton || !status) return;

  async function savePreferences() {
    saveButton.disabled = true;
    resetButton.disabled = true;
    status.textContent = "Saving…";

    try {
      const response = await fetch("/api/metadata-preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preferences: {
            camera_details: cameraDetails.checked,
            gps_location: gpsLocation.checked,
            include_json: includeJson.checked,
          },
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) {
        throw new Error(result.detail || "Could not save preferences.");
      }
      status.textContent = "Saved on this device";
    } catch (error) {
      status.textContent = error.message || "Could not save preferences.";
    } finally {
      saveButton.disabled = false;
      resetButton.disabled = false;
    }
  }

  saveButton.addEventListener("click", savePreferences);
  resetButton.addEventListener("click", () => {
    cameraDetails.checked = true;
    gpsLocation.checked = true;
    includeJson.checked = false;
    savePreferences();
  });
})();