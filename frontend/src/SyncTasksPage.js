import React, {useEffect, useState} from "react";
import api from "./tools/authService";
import SyncTask from "./tools/SyncTask";
import {completedStatuses} from "./tools/constants";
import ManualSync from "./components/ManualSync";
import SyncTasksList from "./components/SyncTasksList";

const SyncTasksPage = ({userData}) => {
    const [syncTasks, setSyncTasks] = useState([]);
    const [meetingId, setMeetingId] = useState(null);
    const [isDisabled, setIsDisabled] = useState(false);

    useEffect(() => {
        const fetchSyncTasks = async () => {
            try {
                const response = await api.get("/sync");
                setSyncTasks(response.data.map(st => new SyncTask(st.task_id, st.meeting_id, st.status, updateSyncJobs)));
            } catch (error) {
                console.error("Error fetching sync jobs:", error);
            }
        };

        fetchSyncTasks();
    }, []);

    useEffect(() => {
        setIsDisabled(isTaskInProgress() || !meetingId);
    }, [meetingId, syncTasks]);

    const safeSetMeetingId = (value) => {
        const parsedValue = value !== null ? parseInt(value, 10) : null;
        setMeetingId(isNaN(parsedValue) ? null : parsedValue);
    };

    const isTaskInProgress = () => {
        return syncTasks.some(
            (task) => task.meetingId === meetingId && !completedStatuses.includes(task.status)
        );
    };

    const syncToCRM = async () => {
        if (!meetingId) return alert("Enter a Meeting ID");

        if (isTaskInProgress()) {
            // This should never happen because the buttong should've been disabled but... meh
            alert("A sync task for this meeting ID is already in progress.");
            return;
        }

        try {
            const response = await api.post(`/sync/${meetingId}/start`);
            const {task_id, meeting_id, status} = response.data;
            const newTask = new SyncTask(task_id, meeting_id, status, updateSyncJobs);
            setSyncTasks(prev => [...prev, newTask]);
        } catch (error) {
            console.error("Error starting sync:", error);
        }
    };

    const updateSyncJobs = (updatedTask) => {
        setSyncTasks(prev =>
            prev.map(task => (task.task_id === updatedTask.task_id ? updatedTask : task))
        );
    };

    return (
        <div>
            {userData?.permissions?.can_manually_sync ? (
                <ManualSync
                    meetingId={meetingId}
                    setMeetingId={safeSetMeetingId}
                    syncToCRM={syncToCRM}
                    isDisabled={isDisabled}
                />
            ) : (
                <p>You do not have permission to manually sync.</p>
            )}

            <SyncTasksList syncTasks={syncTasks}/>
        </div>
    );
};

export default SyncTasksPage;
