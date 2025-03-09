import axios from "axios";
import {jwtDecode} from "jwt-decode";

const API_URL = "http://localhost:8000";
const accessTokenKey = "accessToken";
const refreshTokenKey = "refreshToken";

export const login = async (username, password) => {
  try {
    const response = await axios.post(
      `${API_URL}/login`,
      new URLSearchParams({ username, password }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );

    storeTokens(response.data.access_token, response.data?.refresh_token || null);
    window.dispatchEvent(new Event("authChange"));
    return true;
  } catch (error) {
    console.error("Login failed:", error);
    return false;
  }
};

// Function to store new tokens
const storeTokens = (access, refresh) => {
  localStorage.setItem(accessTokenKey, access);
  localStorage.setItem(refreshTokenKey, refresh);
};

// Function to get stored tokens
const getTokens = () => ({
  access: localStorage.getItem(accessTokenKey),
  refresh: localStorage.getItem(refreshTokenKey),
});

export const getLoggedUser = () => {
  const tokens = getTokens();
  if (!tokens.access) {
    return null;
  }

  const access = jwtDecode(tokens.access);
  if (access.exp * 1000 < Date.now()) {
    console.warn("Token expired. Logging out.");
    logout();
    return null;
  }
  // Else... we are logged in properly
  console.log("Checkpoint tokens", access, tokens.refresh);
  return access;
};

export const logout = () => {
  console.log("Logging out...");
  localStorage.removeItem(accessTokenKey);
  localStorage.removeItem(refreshTokenKey);
  window.dispatchEvent(new Event("authChange"));
};

// Create Axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Axios request interceptor to add access token
api.interceptors.request.use(
  (config) => {
    const { access } = getTokens();
    if (access) {
      config.headers.Authorization = `Bearer ${access}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Axios response interceptor to handle token expiration
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const { refresh } = getTokens();
      if (!refresh) {
        logout();
        return Promise.reject(error);
      }
      try {
        // Request new access token
        const response = await axios.post(`${API_URL}/refresh`, { refresh_token: refresh });
        const newAccessToken = response.data.access_token;
        storeTokens(newAccessToken, refresh);

        // Retry the original request with the new access token
        error.config.headers.Authorization = `Bearer ${newAccessToken}`;
        return api.request(error.config);
      } catch (refreshError) {
        logout();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
