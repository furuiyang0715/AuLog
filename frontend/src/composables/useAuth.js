import { ref } from "vue";
import { api, setToken } from "../api/client";

export function useAuth() {
  const user = ref(null);
  const loading = ref(true);

  async function bootstrap() {
    loading.value = true;
    const token = localStorage.getItem("aulog_token");
    if (!token) {
      user.value = null;
      loading.value = false;
      return;
    }
    try {
      const me = await api("/auth/me");
      user.value = { id: me.id, username: me.username };
    } catch {
      setToken("");
      user.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function login(username, password) {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setToken(data.token);
    user.value = { username: data.username };
    return data;
  }

  async function register(username, password) {
    const data = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setToken(data.token);
    user.value = { username: data.username };
    return data;
  }

  function logout() {
    setToken("");
    user.value = null;
  }

  return { user, loading, bootstrap, login, register, logout };
}
