import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await api("GET", "/auth/me"));
        } catch {
          setToken("");
        }
      }
      setLoading(false);
    })();
  }, []);

  async function login(email, password) {
    const r = await api("POST", "/auth/login", { email, password });
    setToken(r.access_token);
    setUser(await api("GET", "/auth/me"));
  }

  async function register(email, password, full_name) {
    await api("POST", "/auth/register", { email, password, full_name });
  }

  function logout() {
    setToken("");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
