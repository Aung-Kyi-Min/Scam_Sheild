const express = require("express");
const axios = require("axios");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const multer = require("multer");
const FormData = require("form-data");
const { v4: uuidv4 } = require("uuid");
const crypto = require("crypto");

const app = express();
app.use(cors());
app.use(express.json());
app.use("/audio", express.static(path.join(__dirname, "audio")));

// Simple in-memory user storage (in production, use a database)
const USERS_FILE = path.join(__dirname, "users.json");
const SESSIONS_FILE = path.join(__dirname, "sessions.json");

// Load users from file
function loadUsers() {
  if (fs.existsSync(USERS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(USERS_FILE, "utf8"));
    } catch (e) {
      return {};
    }
  }
  return {};
}

// Save users to file
function saveUsers(users) {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2));
}

// Load sessions from file
function loadSessions() {
  if (fs.existsSync(SESSIONS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(SESSIONS_FILE, "utf8"));
    } catch (e) {
      return {};
    }
  }
  return {};
}

// Save sessions to file
function saveSessions(sessions) {
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2));
}

// Simple password hashing (in production, use bcrypt)
function hashPassword(password) {
  return crypto.createHash("sha256").update(password).digest("hex");
}

// Generate session token
function generateToken() {
  return crypto.randomBytes(32).toString("hex");
}

// Middleware to check authentication
function requireAuth(req, res, next) {
  const token = req.headers.authorization?.replace("Bearer ", "") || req.body.token || req.query.token;
  
  if (!token) {
    return res.status(401).json({ error: "Authentication required" });
  }
  
  const sessions = loadSessions();
  const session = sessions[token];
  
  if (!session || session.expires < Date.now()) {
    // Clean up expired session
    if (sessions[token]) {
      delete sessions[token];
      saveSessions(sessions);
    }
    return res.status(401).json({ error: "Invalid or expired token" });
  }
  
  req.user = session.user;
  next();
}

// Auth endpoints
app.post("/api/auth/signup", async (req, res) => {
  try {
    const { email, password, name } = req.body;
    
    if (!email || !password) {
      return res.status(400).json({ error: "Email and password are required" });
    }
    
    const users = loadUsers();
    
    if (users[email]) {
      return res.status(400).json({ error: "User already exists" });
    }
    
    // Create user
    users[email] = {
      email,
      password: hashPassword(password),
      name: name || email,
      createdAt: new Date().toISOString(),
    };
    
    saveUsers(users);
    
    // Don't create session - user needs to log in manually after signup
    res.json({
      success: true,
      message: "Account created successfully. Please log in.",
    });
  } catch (err) {
    console.error("Signup error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/api/auth/login", async (req, res) => {
  try {
    const { email, password } = req.body;
    
    if (!email || !password) {
      return res.status(400).json({ error: "Email and password are required" });
    }
    
    const users = loadUsers();
    const user = users[email];
    
    if (!user || user.password !== hashPassword(password)) {
      return res.status(401).json({ error: "Invalid email or password" });
    }
    
    // Create session
    const token = generateToken();
    const sessions = loadSessions();
    sessions[token] = {
      user: { email, name: user.name },
      expires: Date.now() + 30 * 24 * 60 * 60 * 1000, // 30 days
    };
    saveSessions(sessions);
    
    res.json({
      success: true,
      token,
      user: { email, name: user.name },
    });
  } catch (err) {
    console.error("Login error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/api/auth/logout", (req, res) => {
  try {
    const token = req.headers.authorization?.replace("Bearer ", "") || req.body.token;
    
    if (token) {
      const sessions = loadSessions();
      if (sessions[token]) {
        delete sessions[token];
        saveSessions(sessions);
      }
    }
    
    res.json({ success: true });
  } catch (err) {
    console.error("Logout error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.get("/api/auth/check", (req, res) => {
  try {
    const token = req.headers.authorization?.replace("Bearer ", "") || req.query.token;
    
    if (!token) {
      return res.json({ authenticated: false });
    }
    
    const sessions = loadSessions();
    const session = sessions[token];
    
    if (!session || session.expires < Date.now()) {
      if (sessions[token]) {
        delete sessions[token];
        saveSessions(sessions);
      }
      return res.json({ authenticated: false });
    }
    
    res.json({
      authenticated: true,
      user: session.user,
    });
  } catch (err) {
    console.error("Auth check error:", err);
    res.json({ authenticated: false });
  }
});

const PY_AI_URL = process.env.PY_AI_URL || "http://127.0.0.1:9001"; // Python AI service

// Configure multer for file uploads
const upload = multer({
  dest: path.join(__dirname, "temp"),
  limits: {
    fileSize: 50 * 1024 * 1024, // 50MB max
  },
});

// Ensure temp directory exists
const tempDir = path.join(__dirname, "temp");
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}

async function callAIService(data, options = {}) {
  // call python AI microservice
  const formData = new FormData();
  
  if (data.type === "text") {
    formData.append("text", data.text);
    formData.append("type", "text");
  } else if (data.type === "image" || data.type === "voice") {
    // For file uploads, we'll send as multipart
    const fileStream = fs.createReadStream(data.filePath);
    const fileName = data.fileName || "file";
    formData.append("file", fileStream, fileName);
    formData.append("type", data.type);
  }
  
  // Add options
  if (Object.keys(options).length > 0) {
    formData.append("options", JSON.stringify(options));
  }

  try {
    const resp = await axios.post(`${PY_AI_URL}/predict`, formData, {
      headers: formData.getHeaders(),
      timeout: 120000, // 2 minute timeout for audio processing
    });
    
    return resp.data;
  } catch (axiosError) {
    // Handle axios errors with better messages
    if (axiosError.code === 'ECONNREFUSED') {
      throw new Error(`Cannot connect to AI service at ${PY_AI_URL}. Make sure the Python AI service is running.`);
    } else if (axiosError.code === 'ETIMEDOUT') {
      throw new Error('AI service request timed out. The audio file may be too large or the service is overloaded.');
    } else if (axiosError.response) {
      // Server responded with error status
      const errorMsg = axiosError.response.data?.detail || axiosError.response.data?.error || axiosError.response.statusText;
      throw new Error(`AI service error: ${errorMsg}`);
    } else {
      throw new Error(`AI service error: ${axiosError.message || 'Unknown error'}`);
    }
  }
}

// Handle both JSON and multipart form data
app.post("/api/check", upload.single("file"), async (req, res) => {
  try {
    // Check if it's a JSON request (text-only, backward compatibility)
    const contentType = req.headers["content-type"] || "";
    if (contentType.includes("application/json") && req.body.text && !req.body.type) {
      const { text } = req.body;
      if (!text || typeof text !== "string" || text.trim().length === 0) {
        return res.status(400).json({ error: "text is required" });
      }
      
      try {
        const aiResult = await callAIService({ type: "text", text });
        
        // Handle audio URL if present
        let audioUrl = null;
        if (aiResult.audio_base64) {
          const audioBuffer = Buffer.from(aiResult.audio_base64, "base64");
          const id = uuidv4();
          const audioDir = path.join(__dirname, "audio");
          if (!fs.existsSync(audioDir)) {
            fs.mkdirSync(audioDir, { recursive: true });
          }
          const filePath = path.join(audioDir, `${id}.mp3`);
          fs.writeFileSync(filePath, audioBuffer);
          audioUrl = `/audio/${id}.mp3`;
        }

        return res.json({
          risk_score: aiResult.risk_score,
          label: aiResult.label,
          explanation: aiResult.explanation,
          recommended_action: aiResult.recommended_action,
          audio_url: audioUrl
        });
      } catch (aiError) {
        throw aiError;
      }
    }

    // Handle multipart form data (text, image, or voice)
    const type = req.body.type || (req.body.text ? "text" : null);
    
    if (!type) {
      return res.status(400).json({ error: "type is required (text, image, or voice)" });
    }

    let aiResult;
    let tempFilePath = null;

    try {
      if (type === "text") {
        const text = req.body.text || req.body.content;
        if (!text || typeof text !== "string" || text.trim().length === 0) {
          return res.status(400).json({ error: "text is required" });
        }
        aiResult = await callAIService({ type: "text", text });
      } else if (type === "image" || type === "voice") {
        // Require authentication for image and voice checking
        const token = req.headers.authorization?.replace("Bearer ", "") || req.body.token;
        if (!token) {
          return res.status(401).json({ 
            error: "Authentication required for image and voice checking. Please sign up or log in.",
            requiresAuth: true 
          });
        }
        
        const sessions = loadSessions();
        const session = sessions[token];
        
        if (!session || session.expires < Date.now()) {
          if (sessions[token]) {
            delete sessions[token];
            saveSessions(sessions);
          }
          return res.status(401).json({ 
            error: "Invalid or expired token. Please log in again.",
            requiresAuth: true 
          });
        }
        
        if (!req.file) {
          return res.status(400).json({ error: `${type} file is required` });
        }
        tempFilePath = req.file.path;
        aiResult = await callAIService({
          type: type,
          filePath: tempFilePath,
          fileName: req.file.originalname,
        });
      } else {
        return res.status(400).json({ error: "Invalid type. Must be 'text', 'image', or 'voice'" });
      }

      // Clean up temp file
      if (tempFilePath && fs.existsSync(tempFilePath)) {
        fs.unlinkSync(tempFilePath);
      }

      // if AI returned base64 audio, save it and return a URL
      let audioUrl = null;
      if (aiResult.audio_base64) {
        const audioBuffer = Buffer.from(aiResult.audio_base64, "base64");
        const id = uuidv4();
        const audioDir = path.join(__dirname, "audio");
        if (!fs.existsSync(audioDir)) {
          fs.mkdirSync(audioDir, { recursive: true });
        }
        const filePath = path.join(audioDir, `${id}.mp3`);
        fs.writeFileSync(filePath, audioBuffer);
        audioUrl = `/audio/${id}.mp3`;
      }

      const response = {
        risk_score: aiResult.risk_score,
        label: aiResult.label,
        explanation: aiResult.explanation,
        recommended_action: aiResult.recommended_action,
        audio_url: audioUrl
      };

      res.json(response);
    } catch (aiError) {
      // Clean up temp file on error
      if (tempFilePath && fs.existsSync(tempFilePath)) {
        fs.unlinkSync(tempFilePath);
      }
      throw aiError;
    }
  } catch (err) {
    console.error("Error /api/check:", err);
    const errorMessage = err instanceof Error ? err.message : String(err) || "Internal error";
    res.status(500).json({ 
      error: errorMessage,
      message: errorMessage,
      risk_score: 0,
      label: "error"
    });
  }
});

const PORT = process.env.PORT || 3001; // Use 3001 to avoid conflict with frontend on 3000
app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
  console.log(`Python AI service expected at: ${PY_AI_URL}`);
});
