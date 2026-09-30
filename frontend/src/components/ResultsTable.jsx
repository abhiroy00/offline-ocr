import { useMemo, useState } from "react";

const COLUMNS = [
  { key: "file", label: "File" },
  { key: "company_name", label: "Name of Share" },
  { key: "present_folio_no", label: "Folio No" },
  { key: "registered_folio_no", label: "Registered Folio No" },
  { key: "certificate_no", label: "Certificate No" },
  { key: "share_holder_name", label: "Name of Share Holder" },
  { key: "number_of_shares", label: "No of Shares" },
  { key: "face_value", label: "Face Value / Share" },
  { key: "share_type", label: "Share Type" },
];

export default function ResultsTable({ results, onDeleteSelected, onClearAll }) {
  const [selected, setSelected] = useState(new Set());
  const [filter, setFilter] = useState("all"); // all | needs_review
  const [showAddOnMissing, setShowAddOnMissing] = useState(false);
  const [showNeedsReview, setShowNeedsReview] = useState(false);

  const filtered = useMemo(() => {
    return results.filter((r) => {
      if (filter === "failed" && r.validation_status !== "failed") return false;
      if (showNeedsReview && !r.needs_review) return false;
      if (showAddOnMissing && !(r.validation_flags || "").includes("Add-on not captured")) return false;
      return true;
    });
  }, [results, filter, showNeedsReview, showAddOnMissing]);

  function toggleAll() {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((r) => r.id)));
    }
  }

  function toggleOne(id) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold">
          Results <span className="text-sm font-normal text-gray-500">{filtered.length} Records</span>
        </h2>
        <div className="flex items-center gap-2 text-sm">
          <label className="flex items-center gap-1">
            <input type="radio" name="filter" checked={filter === "all"} onChange={() => setFilter("all")} />
            All
          </label>
          <label className="flex items-center gap-1">
            <input type="radio" name="filter" checked={filter === "failed"} onChange={() => setFilter("failed")} />
            Failed
          </label>
        </div>
      </div>

      <div className="flex items-center gap-4 text-sm">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showAddOnMissing} onChange={(e) => setShowAddOnMissing(e.target.checked)} />
          add-on not captured
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showNeedsReview} onChange={(e) => setShowNeedsReview(e.target.checked)} />
          needs review
        </label>
      </div>

      <div className="flex items-center gap-2">
        <button onClick={toggleAll} className="border rounded px-3 py-1.5 text-sm bg-gray-50 hover:bg-gray-100">
          Select all
        </button>
        <button
          onClick={() => {
            onDeleteSelected(Array.from(selected));
            setSelected(new Set());
          }}
          disabled={selected.size === 0}
          className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded px-3 py-1.5 text-sm"
        >
          Delete selected
        </button>
        <button onClick={onClearAll} className="border rounded px-3 py-1.5 text-sm bg-gray-50 hover:bg-gray-100">
          Clear all
        </button>
        <span className="text-sm text-gray-500 ml-auto">
          {selected.size > 0 ? `${selected.size} selected` : "Nothing selected"}
        </span>
      </div>

      <div className="overflow-x-auto border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2 text-left w-10">
                <input
                  type="checkbox"
                  checked={filtered.length > 0 && selected.size === filtered.length}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-3 py-2 text-left">#</th>
              {COLUMNS.map((c) => (
                <th key={c.key} className="px-3 py-2 text-left whitespace-nowrap">
                  {c.label}
                </th>
              ))}
              <th className="px-3 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <tr key={row.id} className={"border-t " + (row.needs_review ? "bg-amber-50" : "")}>
                <td className="px-3 py-2">
                  <input type="checkbox" checked={selected.has(row.id)} onChange={() => toggleOne(row.id)} />
                </td>
                <td className="px-3 py-2 text-gray-500">{i + 1}</td>
                {COLUMNS.map((c) => (
                  <td key={c.key} className="px-3 py-2 whitespace-nowrap">
                    {c.key === "file" ? (
                      row.file_url ? (
                        <a href={row.file_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                          {row.file}
                        </a>
                      ) : (
                        row.file
                      )
                    ) : (
                      row[c.key] ?? <span className="text-gray-300">—</span>
                    )}
                  </td>
                ))}
                <td className="px-3 py-2">
                  {row.needs_review ? (
                    <span className="text-amber-700 text-xs font-medium">⚠ Needs review</span>
                  ) : (
                    <span className="text-green-700 text-xs font-medium">✓ OK</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length + 3} className="px-3 py-6 text-center text-gray-400">
                  No records yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-500">Click a file name to open its uploaded scan.</p>
    </div>
  );
}
