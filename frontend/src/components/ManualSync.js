import React from "react";

const ManualSync = ({ meetingId, setMeetingId, syncToCRM, isDisabled }) => {
    return (
        <div>
            <h1>Sync to CRM</h1>
            <input
                type="text"
                placeholder="Enter Meeting ID"
                value={meetingId}
                onChange={(e) => setMeetingId(e.target.value)}
            />
            <button onClick={syncToCRM} disabled={isDisabled}>Sync to CRM</button>
        </div>
    );
};

export default ManualSync;
