import React, {useEffect, useState} from "react";
import LoginComponent from "./components/LoginComponent";
import SyncTasksPage from "./SyncTasksPage";
import {getLoggedUser, logout} from "./tools/authService";

const App = () => {
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    const checkAuth = () => {
      const userData = getLoggedUser();
      setUserData(userData);
    };

    checkAuth();
    window.addEventListener("authChange", checkAuth);

    return () => {
      window.removeEventListener("authChange", checkAuth);
    };
  }, []);

  return (
    <div>
      {userData ? (
        <>
          <button onClick={logout} style={{ marginBottom: "10px" }}>Logout</button>
          <SyncTasksPage userData={userData} />
        </>
      ) : (
        <LoginComponent />
      )}
    </div>
  );
};

export default App;
