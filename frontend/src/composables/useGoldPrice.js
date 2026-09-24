import { computed, ref } from "vue";
import { api } from "../api/client";

export function useGoldPrice() {
  const goldPrice = ref(null);
  const goldLoading = ref(false);

  const currentGold = computed(() => {
    const price = goldPrice.value?.price;
    if (price == null || price === "") return null;
    const n = Number(price);
    return Number.isFinite(n) ? n : null;
  });

  async function loadGoldPrice(force = false) {
    goldLoading.value = true;
    try {
      const query = force ? "?refresh=1" : "";
      goldPrice.value = await api(`/stats/gold-price${query}`);
      return currentGold.value;
    } finally {
      goldLoading.value = false;
    }
  }

  return { goldPrice, goldLoading, currentGold, loadGoldPrice };
}
