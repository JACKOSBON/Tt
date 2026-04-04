const TelegramBot = require("node-telegram-bot-api");
const mongoose = require("mongoose");
const config = require("./config");
const { User, Message, Session } = require("./models");

const bot = new TelegramBot(config.BOT_TOKEN, { polling: true });

// ─── MongoDB Connect ─────────────────────────────────────────────────────────
mongoose
  .connect(config.MONGODB_URI)
  .then(() => console.log("✅ MongoDB connected"))
  .catch((err) => console.error("❌ MongoDB error:", err));

// ─── Helpers ─────────────────────────────────────────────────────────────────
const isAdmin = (chatId) => config.ADMIN_IDS.includes(String(chatId));

async function getOrCreateUser(msg) {
  const { id, first_name, last_name, username } = msg.from;
  let user = await User.findOne({ telegramId: String(id) });
  if (!user) {
    user = await User.create({
      telegramId: String(id),
      firstName: first_name,
      lastName: last_name || "",
      username: username || "",
    });
  }
  return user;
}

async function getActiveSession(userId) {
  return Session.findOne({ userId, status: "open" }).sort({ createdAt: -1 });
}

// ─── /start ───────────────────────────────────────────────────────────────────
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;

  if (isAdmin(chatId)) {
    return bot.sendMessage(
      chatId,
      `👑 *Admin Panel*\n\nCommands:\n/users — All users list\n/sessions — Open sessions\n/reply <userId> <message> — Reply to user\n/close <sessionId> — Close a session\n/broadcast <message> — Message all users`,
      { parse_mode: "Markdown" }
    );
  }

  await getOrCreateUser(msg);
  bot.sendMessage(
    chatId,
    `👋 *Welcome!*\n\nYahan apna message likhein — Admin se baat karne ke liye bas type karein.\n\n_Hum jald se jald jawab denge!_ 😊`,
    { parse_mode: "Markdown" }
  );
});

// ─── User → Admin ─────────────────────────────────────────────────────────────
bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  if (msg.text?.startsWith("/")) return;
  if (isAdmin(chatId)) return;

  const user = await getOrCreateUser(msg);

  // Get or create open session
  let session = await getActiveSession(user._id);
  if (!session) {
    session = await Session.create({ userId: user._id });
  }

  // Save message
  await Message.create({
    sessionId: session._id,
    fromUser: true,
    text: msg.text || "[media/sticker]",
    telegramMsgId: msg.message_id,
  });

  // Forward to all admins
  const userInfo = `👤 *${user.firstName} ${user.lastName}* (@${user.username || "no username"})\n🆔 ID: \`${user.telegramId}\`\n📋 Session: \`${session._id}\`\n\n💬 ${msg.text || "[media]"}`;

  for (const adminId of config.ADMIN_IDS) {
    try {
      await bot.sendMessage(adminId, userInfo, {
        parse_mode: "Markdown",
        reply_markup: {
          inline_keyboard: [
            [
              {
                text: "↩️ Reply",
                callback_data: `reply_${user.telegramId}_${session._id}`,
              },
              {
                text: "✅ Close Session",
                callback_data: `close_${session._id}`,
              },
            ],
          ],
        },
      });
    } catch (e) {
      console.error(`Admin ${adminId} ko message nahi gaya:`, e.message);
    }
  }

  bot.sendMessage(chatId, "✅ *Message deliver ho gaya!* Admin jald reply karenge.", {
    parse_mode: "Markdown",
  });
});

// ─── Admin: /reply command ─────────────────────────────────────────────────────
bot.onText(/\/reply (.+)/, async (msg, match) => {
  const chatId = msg.chat.id;
  if (!isAdmin(chatId)) return;

  const parts = match[1].split(" ");
  const targetUserId = parts[0];
  const replyText = parts.slice(1).join(" ");

  if (!targetUserId || !replyText) {
    return bot.sendMessage(chatId, "❌ Format: `/reply <userId> <message>`", {
      parse_mode: "Markdown",
    });
  }

  await sendReplyToUser(chatId, targetUserId, replyText, null);
});

// ─── Inline Button: Reply ──────────────────────────────────────────────────────
bot.on("callback_query", async (query) => {
  const adminChatId = query.message.chat.id;
  const data = query.data;

  if (data.startsWith("reply_")) {
    const [, userId, sessionId] = data.split("_");
    // Store pending reply state
    await Session.findByIdAndUpdate(sessionId, {
      pendingReplyAdmin: String(adminChatId),
    });

    bot.answerCallbackQuery(query.id);
    bot.sendMessage(
      adminChatId,
      `✏️ *User ${userId} ko reply likhein:*\n\nFormat: \`/reply ${userId} <aapka message>\``,
      { parse_mode: "Markdown" }
    );
  }

  if (data.startsWith("close_")) {
    const sessionId = data.split("_")[1];
    await closeSession(sessionId, adminChatId);
    bot.answerCallbackQuery(query.id, { text: "Session close ho gaya ✅" });
  }
});

// ─── Admin: /close ─────────────────────────────────────────────────────────────
bot.onText(/\/close (.+)/, async (msg, match) => {
  if (!isAdmin(msg.chat.id)) return;
  await closeSession(match[1], msg.chat.id);
});

async function closeSession(sessionId, adminChatId) {
  const session = await Session.findByIdAndUpdate(
    sessionId,
    { status: "closed", closedAt: new Date() },
    { new: true }
  );
  if (!session) return bot.sendMessage(adminChatId, "❌ Session nahi mila.");

  const user = await User.findById(session.userId);
  if (user) {
    bot.sendMessage(
      user.telegramId,
      "✅ *Aapki query resolve ho gayi!* Phir kisi bhi waqt message karein. 😊",
      { parse_mode: "Markdown" }
    );
  }
  bot.sendMessage(adminChatId, `✅ Session \`${sessionId}\` close ho gaya.`, {
    parse_mode: "Markdown",
  });
}

async function sendReplyToUser(adminChatId, userId, text, sessionId) {
  try {
    await bot.sendMessage(userId, `💬 *Admin ka jawab:*\n\n${text}`, {
      parse_mode: "Markdown",
    });

    // Save reply in DB
    if (sessionId) {
      await Message.create({
        sessionId,
        fromUser: false,
        text,
      });
    }

    bot.sendMessage(adminChatId, `✅ Reply bhej di gaye user \`${userId}\` ko.`, {
      parse_mode: "Markdown",
    });
  } catch (e) {
    bot.sendMessage(adminChatId, `❌ Reply nahi bheji ja saki: ${e.message}`);
  }
}

// ─── Admin: /users ─────────────────────────────────────────────────────────────
bot.onText(/\/users/, async (msg) => {
  if (!isAdmin(msg.chat.id)) return;
  const users = await User.find().sort({ createdAt: -1 }).limit(20);
  if (!users.length) return bot.sendMessage(msg.chat.id, "Koi user nahi mila.");

  const list = users
    .map(
      (u, i) =>
        `${i + 1}. *${u.firstName} ${u.lastName}* (@${u.username || "-"})\n   ID: \`${u.telegramId}\``
    )
    .join("\n\n");

  bot.sendMessage(msg.chat.id, `👥 *Users (latest 20):*\n\n${list}`, {
    parse_mode: "Markdown",
  });
});

// ─── Admin: /sessions ─────────────────────────────────────────────────────────
bot.onText(/\/sessions/, async (msg) => {
  if (!isAdmin(msg.chat.id)) return;
  const sessions = await Session.find({ status: "open" })
    .populate("userId")
    .sort({ createdAt: -1 });

  if (!sessions.length)
    return bot.sendMessage(msg.chat.id, "✅ Koi open session nahi hai.");

  const list = sessions
    .map(
      (s) =>
        `🟡 *${s.userId?.firstName || "Unknown"}* \n   Session: \`${s._id}\`\n   Opened: ${s.createdAt.toLocaleString("en-IN")}`
    )
    .join("\n\n");

  bot.sendMessage(msg.chat.id, `📋 *Open Sessions:*\n\n${list}`, {
    parse_mode: "Markdown",
  });
});

// ─── Admin: /broadcast ────────────────────────────────────────────────────────
bot.onText(/\/broadcast (.+)/, async (msg, match) => {
  if (!isAdmin(msg.chat.id)) return;
  const text = match[1];
  const users = await User.find();

  let sent = 0,
    failed = 0;
  for (const user of users) {
    try {
      await bot.sendMessage(
        user.telegramId,
        `📢 *Admin ka message:*\n\n${text}`,
        { parse_mode: "Markdown" }
      );
      sent++;
    } catch {
      failed++;
    }
  }

  bot.sendMessage(
    msg.chat.id,
    `📢 Broadcast complete!\n✅ Sent: ${sent}\n❌ Failed: ${failed}`
  );
});

console.log("🤖 Bot chal raha hai...");
