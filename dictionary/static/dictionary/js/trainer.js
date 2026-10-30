/* eSlovari — тренажёр: карточки, квиз, письмо.
   Все тексты вставляются через textContent — никакого innerHTML с данными. */
(function () {
  "use strict";

  var root = document.querySelector("[data-trainer]");
  var dataEl = document.getElementById("trainer-data");
  if (!root || !dataEl) return;

  var data = JSON.parse(dataEl.textContent);
  var cards = data.cards || [];
  if (!cards.length) return;

  var stage = root.querySelector("[data-stage]");
  var counter = root.querySelector("[data-counter]");
  var progress = root.querySelector("[data-progress]");
  var index = 0;
  var correct = 0;
  var mistakes = [];
  var keyHandler = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function button(text, cls, onClick) {
    var b = el("button", "btn " + cls, text);
    b.type = "button";
    b.addEventListener("click", onClick);
    return b;
  }

  function shuffle(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function setKeys(handler) {
    if (keyHandler) document.removeEventListener("keydown", keyHandler);
    keyHandler = handler;
    if (handler) document.addEventListener("keydown", handler);
  }

  function updateProgress() {
    counter.textContent = index + " / " + cards.length;
    progress.style.width = (100 * index / cards.length) + "%";
  }

  function clear() {
    while (stage.firstChild) stage.removeChild(stage.firstChild);
  }

  function next(wasRight) {
    if (wasRight) correct++;
    else mistakes.push(cards[index]);
    index++;
    updateProgress();
    if (index >= cards.length) finish();
    else render();
  }

  // --- Карточки ---------------------------------------------------------------

  function renderCard(card) {
    var flip = el("div", "flip");
    flip.setAttribute("role", "button");
    flip.setAttribute("tabindex", "0");
    flip.setAttribute("aria-label", "Перевернуть карточку");
    var inner = el("div", "flip-inner");
    var front = el("div", "flip-face");
    front.appendChild(el("div", "big-word", card.word));
    if (card.transcription) front.appendChild(el("div", "muted", card.transcription));
    front.appendChild(el("div", "hint", "Нажми, чтобы перевернуть"));
    var back = el("div", "flip-face back");
    back.appendChild(el("div", "big-word", card.translation));
    if (card.description) back.appendChild(el("p", "mt", card.description));
    if (card.example) back.appendChild(el("p", "small", "«" + card.example + "»"));
    inner.appendChild(front);
    inner.appendChild(back);
    flip.appendChild(inner);

    function turn() { flip.classList.toggle("flipped"); }
    flip.addEventListener("click", turn);

    var actions = el("div", "trainer-actions");
    actions.appendChild(button("← Не знаю", "btn-ghost-light", function () { next(false); }));
    actions.appendChild(button("Знаю →", "btn-white", function () { next(true); }));

    stage.appendChild(flip);
    stage.appendChild(actions);
    setKeys(function (e) {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); turn(); }
      else if (e.key === "ArrowLeft") next(false);
      else if (e.key === "ArrowRight") next(true);
    });
  }

  // --- Квиз -------------------------------------------------------------------

  function quizOptions(card) {
    var pool = cards.map(function (c) { return c.translation; })
      .concat(data.distractors || [])
      .filter(function (t) { return t && t !== card.translation; });
    var seen = {};
    var unique = [];
    shuffle(pool).forEach(function (t) {
      if (!seen[t]) { seen[t] = true; unique.push(t); }
    });
    return shuffle([card.translation].concat(unique.slice(0, 3)));
  }

  function renderQuiz(card) {
    var box = el("div", "prompt-box");
    box.appendChild(el("div", "big-word", card.word));
    if (card.transcription) box.appendChild(el("div", "muted", card.transcription));
    stage.appendChild(box);

    var grid = el("div", "quiz-options");
    var feedback = el("div", "feedback");
    feedback.setAttribute("aria-live", "polite");
    var answered = false;
    var buttons = [];

    function choose(i) {
      if (answered || !buttons[i]) return;
      answered = true;
      var ok = buttons[i].dataset.value === card.translation;
      buttons.forEach(function (b) {
        b.disabled = true;
        if (b.dataset.value === card.translation) b.classList.add("right");
      });
      if (!ok) buttons[i].classList.add("wrong");
      feedback.className = "feedback " + (ok ? "ok" : "bad");
      feedback.textContent = ok ? "Верно!" : "Правильно: " + card.translation;
      var go = button(index + 1 < cards.length ? "Дальше →" : "Результат →", "btn-white", function () { next(ok); });
      actions.appendChild(go);
      go.focus();
      setKeys(function (e) { if (e.key === "Enter") { e.preventDefault(); next(ok); } });
    }

    quizOptions(card).forEach(function (text, i) {
      var b = el("button", "option");
      b.type = "button";
      b.dataset.value = text;
      b.appendChild(el("kbd", null, String(i + 1)));
      b.appendChild(document.createTextNode(text));
      b.addEventListener("click", function () { choose(i); });
      buttons.push(b);
      grid.appendChild(b);
    });

    var actions = el("div", "trainer-actions");
    stage.appendChild(grid);
    stage.appendChild(feedback);
    stage.appendChild(actions);
    setKeys(function (e) {
      var n = parseInt(e.key, 10);
      if (n >= 1 && n <= 4) choose(n - 1);
    });
  }

  // --- Письмо -----------------------------------------------------------------

  function normalize(s) {
    return (s || "").toLowerCase().replace(/[’']/g, "'").replace(/[^a-z0-9' -]/g, "")
      .replace(/\s+/g, " ").trim();
  }

  function renderWrite(card) {
    var box = el("div", "prompt-box");
    box.appendChild(el("div", "big-word", card.translation));
    if (card.description) box.appendChild(el("p", "muted small mt", card.description));
    stage.appendChild(box);

    var form = el("form", "write-row");
    var input = el("input");
    input.type = "text";
    input.autocomplete = "off";
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("spellcheck", "false");
    input.setAttribute("aria-label", "Английское слово");
    input.placeholder = "Напишите по-английски…";
    var submit = el("button", "btn btn-white", "Проверить");
    submit.type = "submit";
    form.appendChild(input);
    form.appendChild(submit);

    var feedback = el("div", "feedback");
    feedback.setAttribute("aria-live", "polite");
    var actions = el("div", "trainer-actions");
    var hintLevel = 0;
    var hintBtn = button("Подсказка", "btn-ghost-light btn-sm", function () {
      hintLevel = Math.min(hintLevel + 1, card.word.length);
      feedback.className = "feedback";
      feedback.textContent = "Начинается на: " + card.word.slice(0, hintLevel) + "…";
      input.focus();
    });
    actions.appendChild(hintBtn);

    var done = false;
    var ok = false;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (done) { next(ok); return; }
      if (!input.value.trim()) return;
      done = true;
      ok = normalize(input.value) === normalize(card.word) && hintLevel < card.word.length;
      input.readOnly = true;
      feedback.className = "feedback " + (ok ? "ok" : "bad");
      feedback.textContent = ok ? "Верно! " + card.word : "Правильно: " + card.word;
      submit.textContent = index + 1 < cards.length ? "Дальше →" : "Результат →";
      hintBtn.remove();
      submit.focus();
    });

    stage.appendChild(form);
    stage.appendChild(feedback);
    stage.appendChild(actions);
    setKeys(null);
    input.focus();
  }

  // --- Итог -------------------------------------------------------------------

  function saveResult() {
    if (root.getAttribute("data-logged-in") !== "1" || !window.fetch) return;
    var token = root.querySelector("input[name=csrfmiddlewaretoken]");
    fetch(root.getAttribute("data-result-url"), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token ? token.value : "" },
      body: JSON.stringify({ mode: data.mode, total: cards.length, correct: correct, source: data.source }),
    }).catch(function () {});
  }

  function finish() {
    setKeys(null);
    clear();
    var percent = Math.round(100 * correct / cards.length);
    var wrap = el("div", "center");
    wrap.appendChild(el("div", "result-big", correct + " / " + cards.length));
    wrap.appendChild(el("p", "lead mt", percent >= 90 ? "Отлично! Так держать." :
      percent >= 60 ? "Хороший результат — повторите сложные слова." : "Есть над чем поработать. Попробуйте ещё раз!"));
    stage.appendChild(wrap);

    if (mistakes.length) {
      var list = el("div", "words mt");
      mistakes.forEach(function (c) {
        var w = el("div", "word");
        w.appendChild(el("h3", null, c.word));
        if (c.transcription) w.appendChild(el("div", "tr", c.transcription));
        w.appendChild(el("div", "ru", c.translation));
        list.appendChild(w);
      });
      stage.appendChild(el("p", "center mt", "Слова для повторения:"));
      stage.appendChild(list);
    }

    var actions = el("div", "trainer-actions mt");
    actions.appendChild(button("Ещё раз", "btn-white", function () { window.location.reload(); }));
    var home = el("a", "btn btn-ghost-light", "В словарь");
    home.href = "/#dictionary";
    actions.appendChild(home);
    stage.appendChild(actions);
    saveResult();
  }

  function render() {
    clear();
    var card = cards[index];
    if (data.mode === "quiz") renderQuiz(card);
    else if (data.mode === "write") renderWrite(card);
    else renderCard(card);
  }

  updateProgress();
  render();
})();
