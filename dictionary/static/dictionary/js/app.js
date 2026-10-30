/* eSlovari — общие скрипты: меню, избранное без перезагрузки,
   индикатор надёжности пароля, подтверждения, копирование резервных кодов. */
(function () {
  "use strict";

  // Мобильное меню
  var topbar = document.querySelector("[data-topbar]");
  var toggle = document.querySelector("[data-nav-toggle]");
  if (topbar && toggle) {
    toggle.addEventListener("click", function () {
      var open = topbar.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Избранное: отправляем форму через fetch, без перезагрузки страницы
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("[data-fav]") || !window.fetch) return;
    event.preventDefault();
    var button = form.querySelector(".fav-btn");
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (data) {
        button.setAttribute("aria-pressed", data.active ? "true" : "false");
      })
      .catch(function () {
        form.submit();
      });
  });

  // Подтверждение опасных действий
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var text = form.getAttribute("data-confirm");
    if (text && !window.confirm(text)) event.preventDefault();
  });

  // Индикатор надёжности пароля
  document.querySelectorAll("[data-strength-for]").forEach(function (box) {
    var input = document.getElementById(box.getAttribute("data-strength-for"));
    var bar = box.querySelector(".strength span");
    var label = box.querySelector(".strength-label");
    if (!input) return;
    var levels = [
      { text: "Слишком простой", color: "#e5484d" },
      { text: "Слабый", color: "#f2a516" },
      { text: "Средний", color: "#f2c94c" },
      { text: "Надёжный", color: "#19a463" },
      { text: "Очень надёжный", color: "#0f8a52" },
    ];
    input.addEventListener("input", function () {
      var v = input.value;
      var score = 0;
      if (v.length >= 10) score++;
      if (v.length >= 14) score++;
      if (/[a-zа-яё]/.test(v) && /[A-ZА-ЯЁ]/.test(v)) score++;
      if (/\d/.test(v) && /[^\d]/.test(v)) score++;
      if (/[^A-Za-zА-Яа-яЁё0-9]/.test(v)) score++;
      if (v.length < 10) score = Math.min(score, 1);
      if (/^(.)\1+$/.test(v) || /^(12345|qwerty|password|йцукен)/i.test(v)) score = 0;
      var level = levels[Math.min(score, 4)];
      bar.style.width = v ? ((Math.min(score, 4) + 1) * 20) + "%" : "0";
      bar.style.background = level.color;
      label.textContent = v ? "Надёжность: " + level.text.toLowerCase() : "Надёжность пароля";
    });
  });

  // Копирование резервных кодов
  var copyBtn = document.querySelector("[data-copy-codes]");
  if (copyBtn && navigator.clipboard) {
    copyBtn.addEventListener("click", function () {
      var codes = Array.prototype.map.call(
        document.querySelectorAll("[data-codes] code"),
        function (c) { return c.textContent; }
      );
      navigator.clipboard.writeText("Резервные коды eSlovari:\n" + codes.join("\n")).then(function () {
        copyBtn.textContent = "Скопировано ✓";
      });
    });
  }
})();
