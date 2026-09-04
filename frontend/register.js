"use strict";

/* =====================================================================
 * CONFIG
 * CONFIRM: registration endpoint/shape isn't in the README at all —
 * guessed as POST /auth/register with JSON {name, email, password},
 * returning {access_token, token_type} the same way /token does, so
 * a successful signup can log the user straight into the chat app.
 * If the real endpoint instead just creates the account and expects a
 * separate sign-in step, swap the redirect below for one to "/".
 * ===================================================================== */
const API_BASE = window.location.port === "8000"
  ? ""
  : `${window.location.protocol}//${window.location.hostname}:8000`;
const REGISTER_URL = `${API_BASE}/auth/register`;

const form = document.getElementById("register-form");
const errorEl = document.getElementById("register-error");
const submitBtn = document.getElementById("register-submit");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  const username = document.getElementById("register-email").value.trim();
  const password = document.getElementById("register-password").value;
  const passwordConfirm = document.getElementById("register-password-confirm").value;

  if (password !== passwordConfirm) {
    showError("Passwords don't match.");
    return;
  }
  if (password.length < 8) {
    showError("Password must be at least 8 characters.");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Creating account…";

  try {
    const res = await fetch(REGISTER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(formatApiError(data));
    }

    if (data.access_token) {
      // Auto-login on signup, matching app.js's sessionStorage contract.
      sessionStorage.setItem("authToken", data.access_token);
      window.location.href = "/";
    } else {
      // Backend created the account but didn't hand back a token —
      // send them to sign in manually.
      window.location.href = "/?registered=1";
    }
  } catch (err) {
    showError(err.message || "Registration failed. Please try again.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create account";
  }
});

function formatApiError(data) {
  const detail = data && data.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === "string" ? item : item && item.msg))
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return "Registration failed.";
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}
