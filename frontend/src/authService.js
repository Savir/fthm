import axios from "axios";

const API_URL = "http://backend:8000";
const accessTokenKey = "accessToken";
const refreshTokenKey = "refreshToken";

// Function to get stored tokens
const getTokens = () => ({
  access: localStorage.getItem(accessTokenKey),
  refresh: localStorage.getItem(refreshTokenKey),
});

// Function to store new tokens
const storeTokens = (access, refresh) => {
  localStorage.setItem(accessTokenKey, access);
  localStorage.setItem(refreshTokenKey, refresh);
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
        localStorage.removeItem(accessTokenKey);
        localStorage.removeItem(refreshTokenKey);
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
