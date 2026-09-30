import { useCallback, useEffect, useRef, useState } from "react";
import { api, getAuthToken, setAuthToken } from "./api/client.js";
import Login from "./components/Login.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import JobStatusPanel from "./components/JobStatusPanel.jsx";
import ResultsTable from "./components/ResultsTable.jsx";

export default function App() {
  const [username, setUsername] = useState(null);
  const [files, setFiles] = useState([]);
  const [engine, setEngine] = useState("paddleocr_gpu");
  const [workerCount, setWorkerCount] = useState(8);
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [queuedMessage, setQueuedMessage] = useState("");
  const [systemStatus, setSystemStatus] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    if (getAuthToken()) setUsername("signed in");
    api.systemStatus().then((r) => setSystemStatus(r.data)).catch(() => {});
  }, []);

  const refreshResults = useCallback((jobId) => {
    api.jobResults(jobId).then((r) => setResults(r.data.results ?? r.data));
  }, []);

  const pollJob = useCallback(
    (jobId) => {
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        const r = await api.jobStatus(jobId);
        setJob(r.data);
        refreshResults(jobId);
        if (["complete", "failed", "stopped"].includes(r.data.status)) {
          clearInterval(pollRef.current);
        }
      }, 2000);
    },
    [refreshResults]
  );

  useEffect(() => () => clearInterval(pollRef.current), []);

  async function handleExtract() {
    setQueuedMessage("");
    const uploadResp = await api.upload(files, job?.id);
    const jobId = uploadResp.data.job.id;
    setJob(uploadResp.data.job);
    setQueuedMessage(`${uploadResp.data.documents.length} document(s) queued.`);
    const startResp = await api.startJob(jobId, engine, workerCount);
    setJob(startResp.data);
    pollJob(jobId);
  }

  async function handlePause() {
    if (!job) return;
    const r = await api.pauseJob(job.id);
    setJob(r.data);
  }

  async function handleStop() {
    if (!job) return;
    const r = await api.stopJob(job.id);
    setJob(r.data);
    clearInterval(pollRef.current);
  }

  async function handleDeleteSelected(ids) {
    await api.bulkDeleteCertificates(ids);
    if (job) refreshResults(job.id);
  }

  async function handleClearAll() {
    if (!job) return;
    await api.clearJob(job.id);
    setResults([]);
  }

  function handleLogout() {
    api.logout().catch(() => {});
    setAuthToken(null);
    setUsername(null);
  }

  if (!username) {
    return <Login onLoggedIn={setUsername} />;
  }

  const jobRunning = job && ["queued", "running"].includes(job.status);
  const jobPaused = job?.status === "paused";

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Share Certificate OCR</h1>
          <p className="text-sm text-gray-500">Upload scans, extract details and review results.</p>
        </div>
        <div className="flex items-center gap-3">
          {systemStatus && (
            <span
              className="text-xs px-2 py-1 rounded border"
              title={systemStatus.gpu_name || "CPU"}
            >
              {systemStatus.device === "gpu" ? "🟢 GPU" : "⚪ CPU"} · PaddleOCR
            </span>
          )}
          <a href="/api/ocr/system-status/" className="border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50">
            OCR Status
          </a>
          <button onClick={handleLogout} className="border rounded px-3 py-1.5 text-sm bg-white hover:bg-gray-50">
            Sign out
          </button>
        </div>
      </div>

      <UploadPanel
        files={files}
        onFilesChange={setFiles}
        engine={engine}
        onEngineChange={setEngine}
        workerCount={workerCount}
        onWorkerCountChange={setWorkerCount}
        onExtract={handleExtract}
        onPause={handlePause}
        onStop={handleStop}
        jobRunning={jobRunning}
        jobPaused={jobPaused}
        queuedMessage={queuedMessage}
      />

      {job && <JobStatusPanel job={job} />}

      <ResultsTable results={results} onDeleteSelected={handleDeleteSelected} onClearAll={handleClearAll} />
    </div>
  );
}
