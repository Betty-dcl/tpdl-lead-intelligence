/* Shared "download this view" helpers for the Sales & Recurring tables.
 * Both build their payload from the CURRENTLY DISPLAYED rows (filters applied,
 * in sort order) — WYSIWYG. CSV is built client-side; the designed PDF snapshot
 * is rendered server-side via POST /api/intel/view.pdf. */
(function () {
  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function csvCell(v) {
    let s = (v === null || v === undefined) ? "" : String(v);
    s = s.replace(/\r?\n/g, " ").trim();
    // quote if it contains the delimiter, a quote or a leading/trailing space
    if (/[";]/.test(s) || s.includes('"')) s = '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  // Excel-friendly CSV: UTF-8 BOM + `sep=;` sentinel + semicolon delimiter, so it
  // opens as clean columns with correct accents in any Excel locale (matches the
  // server export). headers = [str]; rows = [[cell, …], …].
  window.tpdlDownloadCsv = function (filename, headers, rows) {
    const lines = ["sep=;", headers.map(csvCell).join(";")];
    for (const r of rows) lines.push(r.map(csvCell).join(";"));
    const content = "﻿" + lines.join("\r\n");
    triggerDownload(new Blob([content], { type: "text/csv;charset=utf-8" }), filename);
  };

  // POST a JSON payload to an endpoint that returns a file, and download it.
  // Used for the rich exports: /export_rich.csv (full-depth CSV for the shown
  // companies) and /view_briefs.pdf (one detailed brief per shown company).
  window.tpdlPostDownload = async function (url, payload) {
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) { alert("Download failed (HTTP " + r.status + ")"); return; }
      triggerDownload(await r.blob(), payload.filename || "tpdl_export");
    } catch (e) {
      alert("Download failed: " + e);
    }
  };

  // Designed PDF snapshot (flat table) of the same view. payload: {title,
  // subtitle, columns, rows, widths?, filename}.
  window.tpdlDownloadViewPdf = async function (payload) {
    window.tpdlPostDownload("/api/intel/view.pdf", payload);
  };
})();
