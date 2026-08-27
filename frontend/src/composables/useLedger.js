import { ref } from "vue";
import { api } from "../api/client";

export function useLedger() {
  const tRecords = ref([]);
  const ingRecords = ref([]);
  const selledRecords = ref([]);
  const allocations = ref([]);
  const bookProjects = ref([]);
  const bookSnapshots = ref([]);
  const loading = ref(false);
  const bookLoading = ref(false);

  async function refreshBook() {
    bookLoading.value = true;
    try {
      const [projects, snapshots] = await Promise.all([
        api("/book/projects"),
        api("/book/snapshots"),
      ]);
      bookProjects.value = projects;
      bookSnapshots.value = snapshots;
    } finally {
      bookLoading.value = false;
    }
  }

  async function refreshAll() {
    loading.value = true;
    try {
      const [t, ing, selled, alloc, projects, snapshots] = await Promise.all([
        api("/t-records"),
        api("/ing-records"),
        api("/selled-records"),
        api("/allocations"),
        api("/book/projects"),
        api("/book/snapshots"),
      ]);
      tRecords.value = t;
      ingRecords.value = ing;
      selledRecords.value = selled;
      allocations.value = alloc;
      bookProjects.value = projects;
      bookSnapshots.value = snapshots;
    } finally {
      loading.value = false;
    }
  }

  async function createT(payload) {
    await api("/t-records", { method: "POST", body: JSON.stringify(payload) });
    await refreshAll();
  }

  async function createIng(payload) {
    await api("/ing-records", { method: "POST", body: JSON.stringify(payload) });
    await refreshAll();
  }

  async function updateT(id, payload) {
    await api(`/t-records/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    await refreshAll();
  }

  async function updateIng(id, payload) {
    await api(`/ing-records/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    await refreshAll();
  }

  async function deleteT(id) {
    await api(`/t-records/${id}`, { method: "DELETE" });
    await refreshAll();
  }

  async function deleteIng(id) {
    await api(`/ing-records/${id}`, { method: "DELETE" });
    await refreshAll();
  }

  async function deleteSelled(id) {
    await api(`/selled-records/${id}`, { method: "DELETE" });
    await refreshAll();
  }

  async function deleteAlloc(id) {
    await api(`/allocations/${id}`, { method: "DELETE" });
    await refreshAll();
  }

  async function matchT(payload) {
    await api("/allocations/t-match", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await refreshAll();
  }

  async function sellFromIng(payload) {
    await api("/allocations/selled", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await refreshAll();
  }

  async function createBookProject(name) {
    await api("/book/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    await refreshBook();
  }

  async function renameBookProject(id, name) {
    await api(`/book/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    await refreshBook();
  }

  async function deleteBookProject(id) {
    await api(`/book/projects/${id}`, { method: "DELETE" });
    await refreshBook();
  }

  async function saveBookSnapshot(date, amounts) {
    await api(`/book/snapshots/${date}`, {
      method: "PUT",
      body: JSON.stringify({ amounts }),
    });
    await refreshBook();
  }

  function targetMark(allocation) {
    if (allocation.target_type === "T_MATCH") {
      return tRecords.value.find((r) => r.id === allocation.target_id)?.mark || "—";
    }
    return selledRecords.value.find((r) => r.id === allocation.target_id)?.mark || "—";
  }

  return {
    tRecords,
    ingRecords,
    selledRecords,
    allocations,
    bookProjects,
    bookSnapshots,
    loading,
    bookLoading,
    refreshAll,
    refreshBook,
    createT,
    createIng,
    updateT,
    updateIng,
    deleteT,
    deleteIng,
    deleteSelled,
    deleteAlloc,
    matchT,
    sellFromIng,
    createBookProject,
    renameBookProject,
    deleteBookProject,
    saveBookSnapshot,
    targetMark,
  };
}
