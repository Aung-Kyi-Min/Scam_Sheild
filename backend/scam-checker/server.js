const express = require("express");
const cors = require("cors");
const path = require("path");

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


app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
