const isWindows = /Windows/i.test(navigator.userAgent);

if (isWindows) {
  const download = document.querySelector("#installer-download");
  const label = document.querySelector("#installer-label");
  const runInstruction = document.querySelector("#run-instruction");
  const approvalInstruction = document.querySelector("#approval-instruction");

  download.href = "downloads/want-installer-windows.zip";
  label.textContent = "Download for Windows";
  runInstruction.innerHTML = "Open the ZIP, then open <strong>install-want-windows.cmd</strong>. It downloads WANT!, copies its folder path, and opens Chrome Extensions.";
  approvalInstruction.innerHTML = "Turn on <strong>Developer mode</strong>, choose <strong>Load unpacked</strong>, paste the copied path into the folder chooser's address bar, and select the folder.";
}
