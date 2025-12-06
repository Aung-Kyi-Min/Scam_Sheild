const express = require("express");
const axios = require("axios");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const multer = require("multer");
const FormData = require("form-data");
const { v4: uuidv4 } = require("uuid");

const app = express();
app.use(cors());
app.use(express.json());
app.use("/audio", express.static(path.join(__dirname, "audio")));

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

  const resp = await axios.post(`${PY_AI_URL}/predict`, formData, {
    headers: formData.getHeaders(),
  });
  
  return resp.data;
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
    res.status(500).json({ error: err.message || "Internal error" });
  }
});

const PORT = process.env.PORT || 3001; // Use 3001 to avoid conflict with frontend on 3000
app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
  console.log(`Python AI service expected at: ${PY_AI_URL}`);
});
