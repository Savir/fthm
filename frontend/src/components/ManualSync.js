import React from "react";

const ManualSync = ({meetingId, setMeetingId, syncToCRM, isDisabled}) => {
    const handleSubmit = (e) => {
        e.preventDefault(); // Prevent page reload
        syncToCRM(); // Trigger the sync function
    };

    return (<div>
        <h1>Sync to CRM</h1>
        <form onSubmit={handleSubmit}>
            <label htmlFor="meeting-id">Meeting ID:</label>
            <input
                type="text"
                placeholder="Enter Meeting ID"
                value={meetingId || ""}
                onChange={(e) => setMeetingId(parseInt(e.target.value, 10))}
            />
            <button type="submit" disabled={isDisabled}>Sync to CRM</button>
        </form>
    </div>);
};

export default ManualSync;
