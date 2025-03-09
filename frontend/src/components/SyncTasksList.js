import React from "react";

const SyncTasksList = ({ syncTasks }) => {
    const sortedTasks = [...syncTasks].sort((a, b) => b.id - a.id);

    return (
        <div>
            <h2>Sync Tasks</h2>
            {syncTasks.length === 0 ? (
                <p>No sync jobs found.</p>
            ) : (
                <ul>
                    {sortedTasks.map((st) => (
                        <li key={st.id}>
                            Sync Job ID {st.id}: Meeting ID {st.meetingId} - Status: {st.status}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default SyncTasksList;
