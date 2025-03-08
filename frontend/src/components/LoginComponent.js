import React, {useState} from "react";
import {login} from "../tools/authService";

const LoginComponent = ({onLogin}) => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(null);

    const handleSubmit = async (event) => {
        event.preventDefault();
        const l = await login(username, password);

        if (!l) {
            setError("Invalid username or password.");
        }
    };

    return (
        <div>
            <h2>Login</h2>
            <form onSubmit={handleSubmit}>
                <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)}
                       required/>
                <input type="password" placeholder="Password" value={password}
                       onChange={(e) => setPassword(e.target.value)} required/>
                <button type="submit">Login</button>
            </form>
            {error && <p style={{color: "red"}}>{error}</p>}
        </div>
    );
};

export default LoginComponent;
