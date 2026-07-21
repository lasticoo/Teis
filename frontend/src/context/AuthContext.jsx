import React, { createContext, useState, useEffect, useContext } from "react";

const AuthContext = createContext(null);

export const API_URL = "http://localhost:8000/api/v1";

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem("token") || null);
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem("token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      localStorage.setItem("token", token);
      setIsAuthenticated(true);
      // Fetch user profile if needed, or parse JWT payload
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUser({ username: payload.sub });
      } catch (e) {
        logout();
      }
    } else {
      localStorage.removeItem("token");
      setIsAuthenticated(false);
      setUser(null);
    }
    setLoading(false);
  }, [token]);

  const login = async (username, password) => {
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Login gagal.");
      }

      const data = await response.json();
      if (data.require_2fa) {
        return { require_2fa: true, sessionToken: data.session_token };
      } else {
        setToken(data.session_token);
        return { require_2fa: false };
      }
    } catch (error) {
      throw error;
    }
  };

  const verify2FA = async (totpCode, sessionToken) => {
    try {
      const response = await fetch(`${API_URL}/auth/verify-2fa`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({ totp_code: totpCode }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Verifikasi 2FA gagal.");
      }

      const data = await response.json();
      setToken(data.access_token);
      return true;
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    setToken(null);
  };

  const getAuthHeader = () => {
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated,
        user,
        loading,
        login,
        verify2FA,
        logout,
        getAuthHeader,
      }}
    >
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
