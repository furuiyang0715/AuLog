import { reactive, watch } from "vue";

export function usePagination(pageSize = 10) {
  const pagination = reactive({
    page: 1,
    pageSize,
    showSizePicker: true,
    pageSizes: [10, 20, 50, 100],
    prefix: ({ itemCount }) => `共 ${itemCount} 条`,
    onUpdatePage: (page) => {
      pagination.page = page;
    },
    onUpdatePageSize: (size) => {
      pagination.pageSize = size;
      pagination.page = 1;
    },
  });

  function resetPage() {
    pagination.page = 1;
  }

  function watchDataLength(dataRef) {
    watch(
      () => dataRef.value?.length ?? 0,
      (len) => {
        const maxPage = Math.max(1, Math.ceil(len / pagination.pageSize) || 1);
        if (pagination.page > maxPage) {
          pagination.page = maxPage;
        }
      }
    );
  }

  return { pagination, resetPage, watchDataLength };
}
