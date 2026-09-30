import { useRef, useState } from "react";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.tiff,.tif,.webp,.bmp";

export default function UploadPanel({
  files,
  onFilesChange,
  engine,
  onEngineChange,
  workerCount,
  onWorkerCountChange,
  onExtract,
  onPause,
  onStop,
  jobRunning,
  jobPaused,
  queuedMessage,
}) {
  const inputRef = useRef(null);
  const folderInputRef = useRef(null);
  const [previews, setPreviews] = useState([]);

  function addFiles(fileList) {
    const incoming = Array.from(fileList);
    const merged = [...files, ...incoming];
    onFilesChange(merged);
    setPreviews((prev) => [
      ...prev,
      ...incoming.map((f) => ({
        name: f.name,
        url: f.type.startsWith("image/") ? URL.createObjectURL(f) : null,
      })),
    ]);
  }

  function removeAt(index) {
    const next = files.filter((_, i) => i !== index);
    onFilesChange(next);
    setPreviews((prev) => prev.filter((_, i) => i !== index));
  }

  function clearSelection() {
    onFilesChange([]);
    setPreviews([]);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <div
        className="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          addFiles(e.dataTransfer.files);
        }}
      >
        <p className="font-medium text-gray-700">Choose certificates</p>
        <p className="text-sm text-gray-500 mt-1">
          PDF, PNG, JPG, TIFF, WEBP or BMP. You can select multiple files.
        </p>
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="border rounded px-4 py-1.5 text-sm bg-gray-50 hover:bg-gray-100"
          >
            Choose Files
          </button>
          <span className="text-sm text-gray-500">{files.length} files</span>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          webkitdirectory=""
          directory=""
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">OCR engine</label>
          <select
            value={engine}
            onChange={(e) => onEngineChange(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          >
            <option value="paddleocr_gpu">PaddleOCR (NVIDIA GPU)</option>
            <option value="paddleocr_cpu">PaddleOCR (CPU)</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Workers</label>
          <input
            type="number"
            min={1}
            max={64}
            value={workerCount}
            onChange={(e) => onWorkerCountChange(Number(e.target.value))}
            className="border rounded px-3 py-1.5 text-sm w-20"
          />
        </div>
        <button
          onClick={onExtract}
          disabled={files.length === 0 || jobRunning}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-1.5 text-sm font-medium self-end"
        >
          Extract
        </button>
        <button
          onClick={() => folderInputRef.current?.click()}
          className="border rounded px-4 py-1.5 text-sm bg-gray-50 hover:bg-gray-100 self-end"
        >
          Select folder
        </button>
        <button
          onClick={onPause}
          disabled={!jobRunning || jobPaused}
          className="border rounded px-4 py-1.5 text-sm bg-gray-50 hover:bg-gray-100 disabled:opacity-50 self-end"
        >
          Pause
        </button>
        <button
          onClick={onStop}
          disabled={!jobRunning}
          className="border border-red-300 text-red-700 rounded px-4 py-1.5 text-sm bg-red-50 hover:bg-red-100 disabled:opacity-50 self-end"
        >
          Stop
        </button>
        <span className="text-sm text-gray-500 self-end">{files.length} file(s) selected</span>
      </div>

      {previews.length > 0 && (
        <div className="flex flex-wrap items-start gap-3">
          {previews.map((p, i) => (
            <div key={i} className="relative">
              <button
                onClick={() => removeAt(i)}
                className="absolute -top-2 -right-2 bg-gray-800 text-white rounded-full w-5 h-5 text-xs leading-5"
                title="Remove"
              >
                ×
              </button>
              <div className="w-24 h-28 border rounded overflow-hidden bg-gray-100 flex items-center justify-center">
                {p.url ? (
                  <img src={p.url} alt={p.name} className="object-cover w-full h-full" />
                ) : (
                  <span className="text-xs text-gray-400 px-1 text-center">{p.name}</span>
                )}
              </div>
              <div className="bg-blue-600 text-white text-xs text-center rounded-b">#{i + 1}</div>
            </div>
          ))}
          <button onClick={clearSelection} className="self-center border rounded px-4 py-1.5 text-sm bg-gray-50 hover:bg-gray-100">
            Clear selection
          </button>
        </div>
      )}

      <p className="text-xs text-gray-500">
        PaddleOCR runs entirely on this server. Scans never leave this machine.
      </p>
      {queuedMessage && <p className="text-sm text-green-700 font-medium">{queuedMessage}</p>}
    </div>
  );
}
