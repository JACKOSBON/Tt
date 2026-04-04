// ─── config.js ────────────────────────────────────────────────────────────────
// .env se values load hoti hain — neeche setup dekhen

require("dotenv").config();

module.exports = {
  BOT_TOKEN:   process.env.BOT_TOKEN,   // BotFather se mila token
  MONGODB_URI: process.env.MONGODB_URI, // MongoDB connection string
  ADMIN_IDS:   (process.env.ADMIN_IDS || "").split(",").map((id) => id.trim()),
  // Multiple admins comma se alag karein: "123456789,987654321"
};
