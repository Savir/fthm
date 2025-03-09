import api from "./authService";
import {completedStatuses} from "./constants";

const WS_URL = "ws://localhost:8000";

class SyncTask {
    constructor(id, meeting_id, status = "in_progress", onUpdate) {
        this.id = parseInt(id, 10);
        this.meetingId = parseInt(meeting_id, 10);
        this.status = status;
        this.onUpdate = onUpdate; // Callback function when status updates
        this.ws = null; // WebSocket instance
        this.pollingInterval = null; // Polling interval ID

        if (this.id && !completedStatuses.includes(this.status)) {
            this.startTracking();
        }
    }

    startTracking() {
        console.log(`Tracking syncTask ID ${this.id} for meeting ${this.meetingId}`);
        this.connectWebSocket();
    }

    connectWebSocket() {
        if (this.ws) {
            console.log(`WebSocket already exists for task ${this.id}`);
            return;
        }
        try {
            this.ws = new WebSocket(`${WS_URL}/ws/sync/${this.id}/status`);

            this.ws.onopen = () => console.log(`WebSocket connected for task ${this.id} at URL ${this.ws.url}`);

            this.ws.onmessage = (event) => {
                const {task_id, status} = JSON.parse(event.data);
                console.log(`Received status update to ${status} for task ${task_id}/${this.id}`);

                if (task_id !== this.id) {
                    console.error(`WebSocket received update for wrong task! Expected ${this.id}, got ${task_id}`);
                    return;
                }

                this.status = status;
                this.onUpdate(this);

                if (completedStatuses.includes(status)) {
                    console.log(`Task ${this.id} has reached completion (${status}), stopping tracking.`);
                    this.stopTracking();
                }
            };

            this.ws.onerror = (error) => {
                console.error(`WebSocket error for task ${this.id}:`, error);
                this.ws.close();
                this.ws = null;
                // Fallback to polling without checking the status This was unexpected... so even if the status
                // is "finished", we should check at least once. Jeez... we're talking about 10 ms or less!
                this.startPolling();
            };

            this.ws.onclose = () => {
                console.log(`WebSocket closed for task ${this.id}`);
                this.ws = null;
                if (!completedStatuses.includes(this.status)) {
                    console.log(`WebSocket closed unexpectedly for task ${this.id}, switching to polling.`);
                    this.startPolling();
                } else {
                    console.log(`WebSocket closed because task ${this.id} is completed, no polling needed.`);
                }
            };
        } catch (error) {
            console.error("WebSocket connection failed", error);
            this.startPolling();
        }
    }

    async fetchStatus() {
        try {
            const response = await api.get(`/sync/${this.id}/status`);
            return response.data;
        } catch (error) {
            console.error(`Error fetching sync status for task ${this.id}:`, error);
            return {status: "error"};
        }
    }

    startPolling() {
        if (this.pollingInterval) return;

        console.log(`Starting polling for task ${this.id}`);
        this.pollingInterval = setInterval(async () => {
            const data = await this.fetchStatus();
            if (data.status !== this.status) {
                this.status = data.status;
                this.onUpdate(this);
            }

            if (completedStatuses.includes(data.status)) {
                console.log(`Task ${this.id} is completed (${data.status}), stopping polling.`);
                this.stopTracking();
            }
        }, 1000);
    }

    stopTracking() {
        // Stop WebSocket if it exists
        if (this.ws) {
            console.log(`Closing WebSocket for task ${this.id}`);
            this.ws.close();
            this.ws = null;
        }

        // Stop polling if it exists
        if (this.pollingInterval) {
            console.log(`Stopping polling for task ${this.id}`);
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}

export default SyncTask;
