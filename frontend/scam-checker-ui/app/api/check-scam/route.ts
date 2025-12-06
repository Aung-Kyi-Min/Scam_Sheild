import { NextRequest, NextResponse } from "next/server";

// Backend API URL - defaults to localhost:3001 (backend server)
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:3001";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const type = formData.get("type") as string;
    const content = formData.get("content") as string | null;
    const file = formData.get("file") as File | null;

    // Validate input
    if (!type) {
      return NextResponse.json(
        { error: "Type is required" },
        { status: 400 }
      );
    }

    // Forward request to backend server
    try {
      const backendFormData = new FormData();
      backendFormData.append("type", type);
      
      if (type === "text") {
        if (!content || !content.trim()) {
          return NextResponse.json(
            { error: "Text content is required" },
            { status: 400 }
          );
        }
        backendFormData.append("text", content);
      } else if (type === "image" || type === "voice") {
        if (!file) {
          return NextResponse.json(
            { error: "File is required" },
            { status: 400 }
          );
        }
        // Validate file size
        const maxSize = type === "image" ? 10 * 1024 * 1024 : 50 * 1024 * 1024;
        if (file.size > maxSize) {
          return NextResponse.json(
            { error: `File size exceeds ${maxSize / 1024 / 1024}MB limit` },
            { status: 400 }
          );
        }
        backendFormData.append("file", file);
      }

      // Forward to backend
      const backendResponse = await fetch(`${BACKEND_URL}/api/check`, {
        method: "POST",
        body: backendFormData,
      });

      if (!backendResponse.ok) {
        const errorText = await backendResponse.text();
        throw new Error(`Backend error: ${backendResponse.status} ${errorText}`);
      }

      const backendData = await backendResponse.json();
      
      // Transform backend response to frontend format
      const isScam = backendData.risk_score >= 60 || backendData.label === "scam";
      
      return NextResponse.json({
        isScam,
        message: backendData.explanation || 
          (isScam 
            ? "⚠️ This appears to be suspicious. Exercise caution."
            : "✅ This appears to be safe. However, always verify independently."),
        details: {
          ...backendData,
          type,
          checkedAt: new Date().toISOString(),
        },
      });
    } catch (backendError: any) {
      console.error("Backend connection error:", backendError);
      // Fallback to local processing if backend is unavailable
      if (type === "text" && content) {
        const isScam = content.toLowerCase().includes("scam") || 
                       content.toLowerCase().includes("free money") ||
                       content.toLowerCase().includes("urgent");
        return NextResponse.json({
          isScam,
          message: isScam
            ? "⚠️ This appears to be suspicious. Exercise caution. (Backend unavailable - using fallback)"
            : "✅ This appears to be safe. However, always verify independently. (Backend unavailable - using fallback)",
          details: {
            type: "text",
            contentLength: content.length,
            checkedAt: new Date().toISOString(),
            error: "Backend unavailable",
          },
        });
      }
      throw backendError;
    }
  } catch (error: any) {
    console.error("Error processing request:", error);
    return NextResponse.json(
      { error: "Internal server error", message: error.message },
      { status: 500 }
    );
  }
}

