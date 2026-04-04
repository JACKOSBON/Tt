const mongoose = require("mongoose");

// ─── User Model ───────────────────────────────────────────────────────────────
const userSchema = new mongoose.Schema(
  {
    telegramId: { type: String, required: true, unique: true },
    firstName:  { type: String, default: "" },
    lastName:   { type: String, default: "" },
    username:   { type: String, default: "" },
    isBlocked:  { type: Boolean, default: false },
  },
  { timestamps: true }
);

// ─── Session Model ─────────────────────────────────────────────────────────────
// Ek session = user ka ek support thread
const sessionSchema = new mongoose.Schema(
  {
    userId:            { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true },
    status:            { type: String, enum: ["open", "closed"], default: "open" },
    closedAt:          { type: Date },
    pendingReplyAdmin: { type: String }, // admin chatId jo reply karne wala hai
  },
  { timestamps: true }
);

// ─── Message Model ─────────────────────────────────────────────────────────────
const messageSchema = new mongoose.Schema(
  {
    sessionId:     { type: mongoose.Schema.Types.ObjectId, ref: "Session", required: true },
    fromUser:      { type: Boolean, required: true }, // true = user ne bheja, false = admin ne
    text:          { type: String, default: "" },
    telegramMsgId: { type: Number },
  },
  { timestamps: true }
);

module.exports = {
  User:    mongoose.model("User",    userSchema),
  Session: mongoose.model("Session", sessionSchema),
  Message: mongoose.model("Message", messageSchema),
};
