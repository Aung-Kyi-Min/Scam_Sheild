const express = require("express");
const cors = require("cors");
const path = require("path");
const fetch = require("node-fetch");
const FormData = require("form-data");
const fs = require("fs");

const app = express();
app.use(cors());
app.use(express.json());
app.use("/audio", express.static(path.join(__dirname, "audio")));

const PORT = process.env.PORT || 3001;



const fs = require("fs");
const multer = require("multer");

// Configure multer upload
const upload = multer({
  dest: path.join(__dirname, "temp"),
  limits: { fileSize: 50 * 1024 * 1024 },
});

// Ensure temp folder exists
const tempDir = path.join(__dirname, "temp");
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}




const PY_AI_URL = process.env.PY_AI_URL || "http://127.0.0.1:9001";

async function callAIService(data, options = {}) {
  const formData = new FormData();

  if (data.type === "text") {
    formData.append("text", data.text);
    formData.append("type", "text");
  } else {
    const fileStream = fs.createReadStream(data.filePath);
    formData.append("file", fileStream, data.fileName || "file");
    formData.append("type", data.type);
  }

  if (Object.keys(options).length > 0) {
    formData.append("options", JSON.stringify(options));
  }

  const resp = await fetch(`${PY_AI_URL}/predict`, {
    method: "POST",
    body: formData,
    headers: formData.getHeaders(),
  });

  if (!resp.ok) {
    throw new Error(`AI service error: ${resp.status} ${await resp.text()}`);
  }

  return resp.json();
}

const { v4: uuidv4 } = require("uuid");
const audioDir = path.join(__dirname, "audio");

function saveAudio(aiResult) {
  if (!aiResult.audio_base64) return null;

  if (!fs.existsSync(audioDir)) {
    fs.mkdirSync(audioDir, { recursive: true });
  }

  const id = uuidv4();
  const filePath = path.join(audioDir, `${id}.mp3`);
  fs.writeFileSync(filePath, Buffer.from(aiResult.audio_base64, "base64"));
  return `/audio/${id}.mp3`;
}

app.post("/api/check", async (req, res, next) => {
    const contentType = req.headers["content-type"] || "";
  
    if (contentType.includes("application/json") && req.body.text && !req.body.type) {
      try {
        const aiResult = await callAIService({ type: "text", text: req.body.text });
        const audioUrl = saveAudio(aiResult);
  
        return res.json({
          risk_score: aiResult.risk_score,
          label: aiResult.label,
          explanation: aiResult.explanation,
          recommended_action: aiResult.recommended_action,
          audio_url: audioUrl,
        });
      } catch (err) {
        return next(err);
      }
    }
  
    return next();
  });
  

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
