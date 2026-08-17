/**
 * I²TMS Login — Client-side JS
 *
 * Responsibilities:
 *   1. Eye-icon toggles password field between type="password" / "text"
 *   2. Inline field validation before submit — shows red text under empty
 *      fields instead of a native browser alert.
 *   3. Shows a loading spinner on the button once both fields pass.
 *
 * NOTE: Client-side checks are UX only. Real auth happens in app.py.
 */

(function () {
  "use strict";

  /* ── Element refs ── */
  const form          = document.getElementById("login-form");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const eyeToggle     = document.getElementById("eye-toggle");
  const eyeOpen       = document.getElementById("eye-open");
  const eyeClosed     = document.getElementById("eye-closed");
  const usernameError = document.getElementById("username-error");
  const passwordError = document.getElementById("password-error");
  const loginBtn      = document.getElementById("login-btn");

  /* ──────────────────────────────────────────────
     1. Eye toggle — password ↔ text
  ────────────────────────────────────────────── */
  if (eyeToggle) {
    eyeToggle.addEventListener("click", function () {
      const isPassword = passwordInput.type === "password";
      passwordInput.type = isPassword ? "text" : "password";

      eyeOpen.classList.toggle("hidden", isPassword);
      eyeClosed.classList.toggle("hidden", !isPassword);
      eyeToggle.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");

      passwordInput.focus();
    });
  }

  /* ──────────────────────────────────────────────
     2. Field error helpers
  ────────────────────────────────────────────── */
  function setError(input, errorEl, msg) {
    errorEl.textContent = msg;
    input.classList.add("input-error");
    input.setAttribute("aria-invalid", "true");
    input.setAttribute("aria-describedby", errorEl.id);
  }

  function clearError(input, errorEl) {
    errorEl.textContent = "";
    input.classList.remove("input-error");
    input.removeAttribute("aria-invalid");
    input.removeAttribute("aria-describedby");
  }

  /* Clear error as the user types */
  usernameInput && usernameInput.addEventListener("input", function () {
    if (usernameInput.value.trim()) clearError(usernameInput, usernameError);
  });

  passwordInput && passwordInput.addEventListener("input", function () {
    if (passwordInput.value) clearError(passwordInput, passwordError);
  });

  /* ──────────────────────────────────────────────
     3. Form submit — validate → show spinner
  ────────────────────────────────────────────── */
  form && form.addEventListener("submit", function (e) {
    let valid = true;

    if (!usernameInput.value.trim()) {
      e.preventDefault();
      setError(usernameInput, usernameError, "Username is required");
      valid = false;
    } else {
      clearError(usernameInput, usernameError);
    }

    if (!passwordInput.value) {
      e.preventDefault();
      setError(passwordInput, passwordError, "Password is required");
      valid = false;
    } else {
      clearError(passwordInput, passwordError);
    }

    if (!valid) {
      // Focus first errored field
      (!usernameInput.value.trim() ? usernameInput : passwordInput).focus();
      return;
    }

    // All good — show loading state
    loginBtn.classList.add("btn-loading");
    loginBtn.disabled = true;
  });

})();
