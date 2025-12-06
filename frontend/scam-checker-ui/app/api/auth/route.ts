import { NextRequest, NextResponse } from "next/server";

// Backend API URL - defaults to localhost:3001 (backend server)
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:3001";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const action = searchParams.get("action") || "check";
    const token = searchParams.get("token");

    if (action === "check") {
      if (!token) {
        return NextResponse.json({ authenticated: false });
      }

      try {
        const response = await fetch(`${BACKEND_URL}/api/auth/check?token=${token}`, {
          method: "GET",
        });

        if (!response.ok) {
          return NextResponse.json({ authenticated: false });
        }

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          console.error("Backend returned non-JSON response");
          return NextResponse.json({ authenticated: false });
        }

        const data = await response.json();
        return NextResponse.json(data);
      } catch (backendError: unknown) {
        console.error("Backend connection error:", backendError);
        return NextResponse.json({ authenticated: false });
      }
    }

    return NextResponse.json(
      { error: "Invalid action for GET request" },
      { status: 400 }
    );
  } catch (error: unknown) {
    console.error("Error processing request:", error);
    return NextResponse.json({ authenticated: false });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, email, password, name, token } = body;

    if (!action) {
      return NextResponse.json(
        { error: "Action is required (signup, login, logout, check)" },
        { status: 400 }
      );
    }

    try {
      if (action === "signup") {
        if (!email || !password) {
          return NextResponse.json(
            { error: "Email and password are required" },
            { status: 400 }
          );
        }

        const response = await fetch(`${BACKEND_URL}/api/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, name }),
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          const text = await response.text();
          console.error("Backend returned non-JSON response:", text.substring(0, 200));
          return NextResponse.json(
            { error: "Backend server error. Please try again." },
            { status: 500 }
          );
        }

        const data = await response.json();
        
        if (!response.ok) {
          return NextResponse.json(data, { status: response.status });
        }

        return NextResponse.json(data);
      } else if (action === "login") {
        if (!email || !password) {
          return NextResponse.json(
            { error: "Email and password are required" },
            { status: 400 }
          );
        }

        const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          const text = await response.text();
          console.error("Backend returned non-JSON response:", text.substring(0, 200));
          return NextResponse.json(
            { error: "Backend server error. Please try again." },
            { status: 500 }
          );
        }

        const data = await response.json();
        
        if (!response.ok) {
          return NextResponse.json(data, { status: response.status });
        }

        return NextResponse.json(data);
      } else if (action === "logout") {
        if (!token) {
          return NextResponse.json({ success: true });
        }

        const response = await fetch(`${BACKEND_URL}/api/auth/logout`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ token }),
        });

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          // Logout can succeed even if backend returns error
          return NextResponse.json({ success: true });
        }

        const data = await response.json();
        return NextResponse.json(data);
      } else if (action === "check") {
        const authToken = token || request.headers.get("authorization")?.replace("Bearer ", "");
        
        if (!authToken) {
          return NextResponse.json({ authenticated: false });
        }

        const response = await fetch(`${BACKEND_URL}/api/auth/check?token=${authToken}`, {
          method: "GET",
        });

        if (!response.ok) {
          return NextResponse.json({ authenticated: false });
        }

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          console.error("Backend returned non-JSON response for auth check");
          return NextResponse.json({ authenticated: false });
        }

        const data = await response.json();
        return NextResponse.json(data);
      } else {
        return NextResponse.json(
          { error: "Invalid action. Use: signup, login, logout, or check" },
          { status: 400 }
        );
      }
    } catch (backendError: unknown) {
      console.error("Backend connection error:", backendError);
      const errorMessage = backendError instanceof Error 
        ? backendError.message 
        : "Backend unavailable";
      return NextResponse.json(
        { error: errorMessage },
        { status: 500 }
      );
    }
  } catch (error: unknown) {
    console.error("Error processing request:", error);
    const errorMessage = error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json(
      { error: "Internal server error", message: errorMessage },
      { status: 500 }
    );
  }
}

