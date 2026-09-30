import { api } from "../api/client.js";

const STATUS_LABEL = {
  queued: "Queued",
  running: "Running",
  paused: "Paused",
  stopped: "Stopped",
  complete: "Complete",
  failed: "Failed",
};

export default function JobStatusPanel({ job }) {
  if (!job) return null;

  const total = job.total_files || 0;
  const done = job.done_count || 0;
  const failed = job.failed_count || 0;
  const waiting = job.waiting_count || 0;
  const pct = total ? Math.round(((done + failed) / total) * 100) : 0;

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Job status</h2>
        <span
          className={
            "text-xs font-medium px-2 py-1 rounded " +
            (job.status === "complete"
              ? "bg-green-100 text-green-700"
              : job.status === "failed"
              ? "bg-red-100 text-red-700"
              : "bg-blue-100 text-blue-700")
          }
        >
          {STATUS_LABEL[job.status] || job.status}
        </span>
      </div>

      <div className="w-full bg-gray-200 rounded h-2 overflow-hidden">
        <div className="bg-blue-600 h-2" style={{ width: `${pct}%` }} />
      </div>

      <div className="text-sm text-gray-600">
        {done} done · {waiting} waiting · {failed} failed
      </div>

      <div className="flex gap-4 text-sm">
        <a className="text-blue-600 hover:underline" href={api.failedExportUrl(job.id)}>
          Download certificates-failed.csv
        </a>
        <a className="text-blue-600 hover:underline" href={api.exportUrl(job.id, "csv")}>
          Download certificates.csv
        </a>
        <a className="text-blue-600 hover:underline" href={api.exportUrl(job.id, "xlsx")}>
          Download certificates.xlsx
        </a>
      </div>
    </div>
  );
}
