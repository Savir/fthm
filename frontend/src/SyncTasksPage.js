import React, {useEffect, useState} from "react";
import api from "./tools/authService";
import SyncTask from "./tools/SyncTask";
import {completedStatuses} from "./tools/constants";
import ManualSync from "./components/ManualSync";
import SyncTasksList from "./components/SyncTasksList";

const SyncTasksPage = ({userData}) => {
    const [syncTasks, setSyncTasks] = useState([]);
    const [meetingId, setMeetingId] = useState("");
    const [isDisabled, setIsDisabled] = useState(false);

    useEffect(() => {
        const fetchSyncTasks = async () => {
            try {
                const response = await api.get("/sync");
                setSyncTasks(response.data.map(st => new SyncTask(st.id, st.meeting_id, st.status, updateSyncJobs)));
            } catch (error) {
                console.error("Error fetching sync jobs:", error);
            }
        };

        fetchSyncTasks();
    }, []);

    const syncToCRM = async () => {
        if (!meetingId) return alert("Enter a Meeting ID");

        const isTaskInProgress = syncTasks.some(
            (task) => task.meetingId === meetingId && !completedStatuses.includes(task.status)
        );

        if (isTaskInProgress) {
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
            prev.map(task => (task.id === updatedTask.id ? updatedTask : task))
        );
    };

    useEffect(() => {
        const isTaskInProgress = syncTasks.some(
            (task) => task.meetingId === meetingId && !completedStatuses.includes(task.status)
        );
        setIsDisabled(isTaskInProgress);
    }, [meetingId, syncTasks]);

    return (
        <div>
            {userData?.permissions?.can_manually_sync ? (
                <ManualSync
                    meetingId={meetingId}
                    setMeetingId={setMeetingId}
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
