import { subscribeToSyncStatus } from "./syncStatusService";
import { completedStatuses } from "./constants";

class SyncTask {
    constructor(id, meeting_id, status = "scheduled", onUpdate) {
        this.id = id;
        this.meetingId = meeting_id;
        this.status = status;
        this.onUpdate = onUpdate; // Callback function when status updates
        this.unsubscribe = null;

        if (!completedStatuses.includes(this.status)) {
            this.startTracking();
        }
    }

    startTracking() {
        console.log(`Tracking syncTask ID ${this.id} for meeting ${this.meetingId}`);
        this.unsubscribe = subscribeToSyncStatus(this.id, (data) => {
            this.status = data.status;
            this.onUpdate(this);

            if (completedStatuses.includes(this.status)) {
                console.log(`Task ${this.id} has reached completion (${this.status}), stopping tracking.`);
                this.stopTracking();
            }
        });
    }

    stopTracking() {
        if (this.unsubscribe) {
            this.unsubscribe(); // Stop WebSocket and polling
            this.unsubscribe = null;
        }
    }
}

export default SyncTask;
