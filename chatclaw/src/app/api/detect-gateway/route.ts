import { NextResponse } from "next/server";

export async function GET() {
  // Gypsea local gateway — bridges OpenClaw protocol to Claude Code CLI
  return NextResponse.json({
    found: true,
    url: "ws://localhost:8765/ws/gateway",
    token: "gypsea-local",
  });
}
