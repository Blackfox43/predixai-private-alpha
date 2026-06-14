import "dotenv/config";
import express, { type NextFunction, type Request, type Response } from "express";
import { GoogleGenAI } from "@google/genai";
import { createServer as createViteServer } from "vite";
import path from "path";
import { promises as fs } from "fs";

const PORT = Number(process.env.PORT ?? 3000);
const GEMINI_MODEL = process.env.GEMINI_MODEL ?? "gemini-2.5-flash";
const CHAT_WINDOW_MS = 60_000;
const CHAT_MAX_REQUESTS_PER_WINDOW = 20;
const ALPHA_ACCESS_PASSWORD = process.env.ALPHA_ACCESS_PASSWORD?.trim();

function fixtureDate(daysAhead: number, hourUtc: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + daysAhead);
  date.setUTCHours(hourUtc, 0, 0, 0);
  return date.toISOString();
}

function requireAlphaAccess(req: Request, res: Response, next: NextFunction): void {
  // In production, setting ALPHA_ACCESS_PASSWORD enables a simple private-alpha gate.
  // For stronger access control, leave this unset and protect the URL with Cloudflare Access.
  if (process.env.NODE_ENV !== "production" || !ALPHA_ACCESS_PASSWORD) {
    next();
    return;
  }

  const header = req.header("authorization") ?? "";
  const [scheme, encodedCredentials] = header.split(" ");

  if (scheme === "Basic" && encodedCredentials) {
    try {
      const decoded = Buffer.from(encodedCredentials, "base64").toString("utf-8");
      const separatorIndex = decoded.indexOf(":");
      const password = separatorIndex >= 0 ? decoded.slice(separatorIndex + 1) : decoded;

      if (password === ALPHA_ACCESS_PASSWORD) {
        next();
        return;
      }
    } catch {
      // Fall through to the 401 below. Do not expose parsing details to the client.
    }
  }

  res.setHeader("WWW-Authenticate", 'Basic realm="PredixAI Private Alpha"');
  res.status(401).send("Private alpha access required.");
}

const matches = [
  {
    id: "1",
    homeTeam: "Arsenal",
    awayTeam: "Liverpool",
    date: fixtureDate(1, 15),
    league: "Premier League",
    predictions: {
      homeWin: 42.5,
      draw: 28.1,
      awayWin: 29.4,
      confidence: "High",
      explanation:
        "Arsenal's xG trend at home is +1.2 over the last 5 matches. Liverpool has a slight fatigue factor due to mid-week European fixtures.",
      keyFactors: [
        { name: "Home Form", impact: "positive", value: "+1.2 xG" },
        { name: "Away Fatigue", impact: "positive", value: "High" },
        { name: "H2H Record", impact: "neutral", value: "Even" },
      ],
    },
    stats: {
      home: { xG: 2.1, possession: 58, shots: 14 },
      away: { xG: 1.8, possession: 52, shots: 12 },
    },
  },
  {
    id: "2",
    homeTeam: "Real Madrid",
    awayTeam: "Barcelona",
    date: fixtureDate(2, 20),
    league: "La Liga",
    predictions: {
      homeWin: 55.2,
      draw: 22.3,
      awayWin: 22.5,
      confidence: "Medium",
      explanation:
        "Real Madrid's home advantage and recent goal-scoring form give them the edge. Barcelona's defense has shown vulnerabilities in away matches.",
      keyFactors: [
        { name: "Home Attack", impact: "positive", value: "Strong" },
        { name: "Away Defense", impact: "negative", value: "Weak" },
        { name: "Injuries", impact: "neutral", value: "None" },
      ],
    },
    stats: {
      home: { xG: 2.5, possession: 55, shots: 16 },
      away: { xG: 1.5, possession: 60, shots: 10 },
    },
  },
  {
    id: "3",
    homeTeam: "Bayern Munich",
    awayTeam: "B. Dortmund",
    date: fixtureDate(3, 17),
    league: "Bundesliga",
    predictions: {
      homeWin: 65.8,
      draw: 18.2,
      awayWin: 16.0,
      confidence: "High",
      explanation:
        "Bayern's dominant home record and superior xG differential make them strong favorites. Dortmund's away form has been inconsistent.",
      keyFactors: [
        { name: "xG Differential", impact: "positive", value: "+1.8" },
        { name: "Home Advantage", impact: "positive", value: "Strong" },
        { name: "Away Form", impact: "negative", value: "Inconsistent" },
      ],
    },
    stats: {
      home: { xG: 3.0, possession: 65, shots: 20 },
      away: { xG: 1.2, possession: 45, shots: 8 },
    },
  },
] as const;

type ChatBody = {
  message?: unknown;
  match?: {
    homeTeam?: unknown;
    awayTeam?: unknown;
    league?: unknown;
    predictions?: {
      homeWin?: unknown;
      draw?: unknown;
      awayWin?: unknown;
      confidence?: unknown;
    };
  } | null;
};

const chatBuckets = new Map<string, { count: number; resetAt: number }>();

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const current = chatBuckets.get(ip);
  if (!current || current.resetAt <= now) {
    chatBuckets.set(ip, { count: 1, resetAt: now + CHAT_WINDOW_MS });
    return false;
  }
  current.count += 1;
  return current.count > CHAT_MAX_REQUESTS_PER_WINDOW;
}

function sanitizeMessage(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > 1_000) return null;
  return trimmed;
}

function matchContext(match: ChatBody["match"]): string {
  if (!match) return "No selected match.";
  const homeTeam = typeof match.homeTeam === "string" ? match.homeTeam : "Home team";
  const awayTeam = typeof match.awayTeam === "string" ? match.awayTeam : "Away team";
  const league = typeof match.league === "string" ? match.league : "Unknown league";
  const p = match.predictions ?? {};
  const homeWin = typeof p.homeWin === "number" ? p.homeWin : "unknown";
  const draw = typeof p.draw === "number" ? p.draw : "unknown";
  const awayWin = typeof p.awayWin === "number" ? p.awayWin : "unknown";
  const confidence = typeof p.confidence === "string" ? p.confidence : "unknown";

  // Keep context small and structured to limit prompt injection surface and token usage.
  return `Selected match: ${homeTeam} vs ${awayTeam}. League: ${league}. Model probabilities: home ${homeWin}%, draw ${draw}%, away ${awayWin}%. Confidence: ${confidence}.`;
}

async function readBacktestResults() {
  const dataPath = path.join(process.cwd(), "data", "backtest_results.json");
  try {
    const raw = await fs.readFile(dataPath, "utf-8");
    return JSON.parse(raw);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw error;
    }
    return {
      metrics: { log_loss: 0.98, brier_score: 0.58, accuracy: 0.54 },
      betting_simulation: {
        starting_bankroll: 1000.0,
        ending_bankroll: 1124.5,
        total_profit: 124.5,
        bets_placed: 150,
        bets_won: 68,
        win_rate: 45.3,
        roi_percentage: 8.3,
      },
    };
  }
}

async function startServer() {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" })); // Prevent oversized chat payloads from tying up memory.

  app.get("/api/health", (_req: Request, res: Response) => {
    res.json({ status: "ok" });
  });

  app.use(requireAlphaAccess); // Protect app pages and APIs when ALPHA_ACCESS_PASSWORD is configured.

  app.get("/api/matches", (_req: Request, res: Response) => {
    res.set("Cache-Control", "no-store");
    res.json(matches);
  });

  app.get("/api/backtest", async (_req: Request, res: Response) => {
    try {
      res.json(await readBacktestResults());
    } catch (error) {
      console.error("Failed to load backtest data", error);
      res.status(500).json({ error: "Failed to load backtest data" });
    }
  });

  app.get("/api/live-tracking", (_req: Request, res: Response) => {
    res.json({
      total_tracked: 42,
      accuracy: 57.1,
      total_profit: 45.2,
      recent_matches: [
        { match: "Arsenal vs Chelsea", predicted: "H", actual: "H", profit: 8.5 },
        { match: "Man Utd vs Spurs", predicted: "D", actual: "A", profit: -10.0 },
        { match: "Liverpool vs Villa", predicted: "H", actual: "H", profit: 4.2 },
      ],
    });
  });

  app.post("/api/chat", async (req: Request<object, object, ChatBody>, res: Response) => {
    const message = sanitizeMessage(req.body?.message);
    if (!message) {
      res.status(400).json({ error: "Message must be a non-empty string under 1,000 characters." });
      return;
    }

    const ip = req.ip ?? req.socket.remoteAddress ?? "unknown";
    if (isRateLimited(ip)) {
      res.status(429).json({ error: "Too many chat requests. Try again shortly." });
      return;
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      res.status(503).json({ error: "AI chat is not configured on the server." });
      return;
    }

    try {
      const ai = new GoogleGenAI({ apiKey });
      const response = await ai.models.generateContent({
        model: GEMINI_MODEL,
        contents: `${matchContext(req.body.match)}\n\nUser question: ${message}`,
        config: {
          systemInstruction:
            "You are an expert football AI analyst. Explain model predictions clearly, never guarantee outcomes, and avoid betting guarantees. Focus on xG, form, rest, fatigue, tactical fit, and uncertainty.",
        },
      });

      res.json({ message: response.text ?? "I could not generate a response." });
    } catch (error) {
      console.error("Chat generation failed", error);
      res.status(502).json({ error: "AI model request failed." });
    }
  });

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath, { maxAge: "1h", index: false }));
    app.get("*", (_req: Request, res: Response) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

import path from "path";

// 1. Serve frontend build
app.use(express.static(path.join(process.cwd(), "dist")));

// 2. React router fallback (VERY IMPORTANT)
app.get("*", (_, res) => {
  res.sendFile(path.join(process.cwd(), "dist", "index.html"));
});

// 3. Start server LAST
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
}

startServer().catch((error) => {
  console.error("Failed to start server", error);
  process.exit(1);
});
