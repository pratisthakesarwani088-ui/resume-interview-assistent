import { createContext, useContext, useEffect, useState } from "react";
import api from "../api/axios.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });
  const [ready, setReady] = useState(false);

  // On first load, if we have tokens, confirm they're valid by pulling the profile.
  useEffect(() => {
    const access = localStorage.getItem("access");
    if (!access) {
      setReady(true);
      return;
    }
    api
      .get("/profile/")
      .then(({ data }) => {
        setUser(data);
        localStorage.setItem("user", JSON.stringify(data));
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setReady(true));
  }, []);

  const signup = async ({ name, email, password, confirm_password }) => {
    await api.post("/signup/", { name, email, password, confirm_password });
  };

  const login = async ({ email, password }) => {
    const { data } = await api.post("/login/", { email, password });
    localStorage.setItem("access", data.access);
    localStorage.setItem("refresh", data.refresh);
    localStorage.setItem("user", JSON.stringify(data.user));
    setUser(data.user);
  };

  const logout = async () => {
    const refresh = localStorage.getItem("refresh");
    try {
      if (refresh) await api.post("/logout/", { refresh });
    } catch {
      // even if the server call fails, still clear local state below
    } finally {
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("user");
      setUser(null);
    }
  };

  const updateProfile = async (payload) => {
    const { data } = await api.patch("/profile/", payload);
    setUser(data);
    localStorage.setItem("user", JSON.stringify(data));
    return data;
  };

  const changePassword = async (payload) => {
    await api.post("/change-password/", payload);
  };

  return (
    <AuthContext.Provider
      value={{ user, ready, signup, login, logout, updateProfile, changePassword }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
