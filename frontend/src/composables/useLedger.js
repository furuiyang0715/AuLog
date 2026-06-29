import { ref } from "vue";
import { api } from "../api/client";

export function useLedger() {
  const tRecords = ref([]);
  const ingRecords = ref([]);
  const selledRecords = ref([]);
  const allocations = ref([]);
  const loading = ref(false);

  async function refreshAll() {
    loading.value = true;
    try {
      const [t, ing, selled, alloc] = await Promise.all([
        api("/t-records"),
        api("/ing-records"),
        api("/selled-records"),
        api("/allocations"),
      ]);
      tRecords.value = t;
      ingRecords.value = ing;
      selledRecords.value = selled;
      allocations.value = alloc;
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
    loading,
    refreshAll,
    createT,
    createIng,
    deleteT,
    deleteIng,
    deleteSelled,
    deleteAlloc,
    matchT,
    sellFromIng,
    targetMark,
  };
}
