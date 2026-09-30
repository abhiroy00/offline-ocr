import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("ocr_token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem("ocr_token", token);
  } else {
    localStorage.removeItem("ocr_token");
  }
}

export function getAuthToken() {
  return localStorage.getItem("ocr_token");
}

export const api = {
  login: (username, password) => client.post("/auth/login/", { username, password }),
  logout: () => client.post("/auth/logout/"),
  systemStatus: () => client.get("/ocr/system-status/"),
  upload: (files, jobId, onProgress) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    if (jobId) form.append("job", jobId);
    return client.post("/ocr/upload/", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: onProgress,
    });
  },
  startJob: (jobId, engine, workerCount) =>
    client.post(`/ocr/jobs/${jobId}/start/`, { engine, worker_count: workerCount }),
  pauseJob: (jobId) => client.post(`/ocr/jobs/${jobId}/pause/`),
  stopJob: (jobId) => client.post(`/ocr/jobs/${jobId}/stop/`),
  jobStatus: (jobId) => client.get(`/ocr/jobs/${jobId}/`),
  jobResults: (jobId, params) => client.get(`/ocr/jobs/${jobId}/results/`, { params }),
  clearJob: (jobId) => client.post(`/ocr/jobs/${jobId}/clear/`),
  bulkDeleteCertificates: (ids) => client.post("/ocr/certificates/bulk-delete/", { ids }),
  exportUrl: (jobId, format = "csv") => `${client.defaults.baseURL}/ocr/jobs/${jobId}/export/?format=${format}`,
  failedExportUrl: (jobId) => `${client.defaults.baseURL}/ocr/jobs/${jobId}/failed-export/`,
  reviewField: (fieldId, data) => client.patch(`/ocr/certificate-fields/${fieldId}/review/`, data),
};

export default client;
