import React from "react";

const SyncTasksList = ({ syncTasks }) => {
    const sortedTasks = [...syncTasks].sort((a, b) => b.task_id - a.task_id);

    return (
        <div>
            <h2>Sync Tasks</h2>
            {syncTasks.length === 0 ? (
                <p>No sync jobs found.</p>
            ) : (
                <ul>
                    {sortedTasks.map((st) => (
                        <li key={st.task_id}>
                            Sync Job ID {st.task_id}: Meeting ID {st.meetingId} - Status: {st.status}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default SyncTasksList;
