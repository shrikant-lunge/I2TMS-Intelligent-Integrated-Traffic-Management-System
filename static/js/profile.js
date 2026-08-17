/**
 * I²TMS — profile.js (Screen 12 Followup: Profile page)
 */

(function () {
  'use strict';

  var btnSubmit = document.getElementById('btn-change-password');
  if (btnSubmit) {
    btnSubmit.addEventListener('click', function (e) {
      e.preventDefault();

      var current = document.getElementById('current-password').value;
      var next = document.getElementById('new-password').value;
      var errorEl = document.getElementById('password-error');
      var successEl = document.getElementById('password-success');

      if (errorEl) errorEl.hidden = true;
      if (successEl) successEl.hidden = true;

      if (!current || !next) {
        if (errorEl) {
          errorEl.textContent = "Both fields are required.";
          errorEl.hidden = false;
        }
        return;
      }

      fetch('/api/change_password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: current, new_password: next })
      })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) { throw new Error(err.error || 'Failed to update password.'); });
        }
        return res.json();
      })
      .then(function () {
        document.getElementById('current-password').value = '';
        document.getElementById('new-password').value = '';
        if (successEl) {
          successEl.hidden = false;
          setTimeout(function () { successEl.hidden = true; }, 4000);
        }
      })
      .catch(function (err) {
        if (errorEl) {
          errorEl.textContent = err.message || 'Something went wrong.';
          errorEl.hidden = false;
        }
      });
    });
  }

})();
