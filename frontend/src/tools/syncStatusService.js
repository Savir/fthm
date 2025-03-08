import api from "./authService";
import {completedStatuses} from "./constants";

const WS_URL = "ws://localhost:8000";
const pollingIntervals = new Map(); // Track active pollers


export const subscribeToSyncStatus = (syncTaskId, callback) => {
    let ws;

    const handleStatusUpdate = (data) => {
        callback(data);
        if (completedStatuses.includes(data.status)) {
            console.log(`Task ${syncTaskId} is completed (${data.status}), stopping tracking.`);
            stopTracking(syncTaskId);
        }
    };

    try {
        ws = new WebSocket(`${WS_URL}/ws/sync/${syncTaskId}/status`);

        ws.onopen = () => console.log(`WebSocket for syncTaskId=${syncTaskId} connected`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleStatusUpdate(data);
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            fallbackToPolling(syncTaskId, handleStatusUpdate);
        };

        ws.onclose = () => {
            console.log("WebSocket closed, switching to polling.");
            fallbackToPolling(syncTaskId, handleStatusUpdate);
        };
    } catch (error) {
        console.error("WebSocket connection failed, falling back to polling:", error);
        fallbackToPolling(syncTaskId, handleStatusUpdate);
    }

    return () => stopTracking(syncTaskId);
};


export const fetchSyncStatus = async (syncTaskId) => {
    try {
        const response = await api.get(`/sync/${syncTaskId}/status`);
        return response.data;
    } catch (error) {
        console.error("Error fetching sync status:", error);
        return {status: "error"};
    }
};

const fallbackToPolling = (syncTaskId, callback) => {
    if (pollingIntervals.has(syncTaskId)) return; // Avoid duplicate polling

    console.log(`Starting polling for ${syncTaskId}`);
    const interval = setInterval(async () => {
        const data = await fetchSyncStatus(syncTaskId);
        callback(data);

        if (completedStatuses.includes(data.status)) {
            console.log(`Task ${syncTaskId} is completed (${data.status}), stopping polling.`);
            stopTracking(syncTaskId);
            return;
        }

    }, 5000);

    pollingIntervals.set(syncTaskId, interval);
};

const stopTracking = (syncTaskId) => {
    if (pollingIntervals.has(syncTaskId)) {
        clearInterval(pollingIntervals.get(syncTaskId));
        pollingIntervals.delete(syncTaskId);
        console.log(`Stopped polling for ${syncTaskId}`);
    }
};
