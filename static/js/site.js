/*
 * Минимальный клиентский слой: модалка заявки, табы карточки и мобильное меню.
 * Всё остальное делает HTMX — отдельного фронтенд-фреймворка проект не требует.
 */
(function () {
  "use strict";

  // Модалка заявки: открывается ссылкой с data-mm-modal, закрывается по Esc,
  // клику по подложке и крестику.
  document.addEventListener("click", function (event) {
    var closer = event.target.closest("[data-mm-modal-close]");
    if (closer) {
      event.preventDefault();
      closeModal();
      return;
    }
    var backdrop = event.target;
    if (backdrop.classList && backdrop.classList.contains("mm-modal")) {
      closeModal();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });

  function closeModal() {
    var root = document.getElementById("mm-modal-root");
    if (root) root.innerHTML = "";
  }

  // Табы карточки техники: «Характеристики», «Комплектация», «Документы».
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-mm-tab]");
    if (!button) return;
    var wrapper = button.closest("[data-mm-tabs]");
    if (!wrapper) return;

    wrapper.querySelectorAll("[data-mm-tab]").forEach(function (item) {
      item.setAttribute("aria-selected", String(item === button));
    });
    var target = button.getAttribute("data-mm-tab");
    wrapper.querySelectorAll("[data-mm-tab-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-mm-tab-panel") !== target;
    });
  });

  // Сравнение моделей.
  //
  // Выбор хранится в localStorage, а не на сервере: сравнение — это черновик
  // мысли, ради которого не нужно ни авторизации, ни записи в базу. В адрес
  // страницы сравнения он попадает параметрами, поэтому подобранный набор
  // можно отправить коллеге ссылкой.
  var COMPARE_KEY = "mm.compare";
  var COMPARE_LIMIT = 4;

  function readCompare() {
    try {
      var raw = window.localStorage.getItem(COMPARE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.slice(0, COMPARE_LIMIT) : [];
    } catch (error) {
      return [];
    }
  }

  function writeCompare(items) {
    try {
      window.localStorage.setItem(COMPARE_KEY, JSON.stringify(items));
    } catch (error) {
      // Приватный режим браузера запрещает запись — сравнение просто не
      // запомнится между страницами, ломать из-за этого ничего не нужно.
    }
    renderCompare();
  }

  function renderCompare() {
    var items = readCompare();
    var bar = document.getElementById("mm-compare-bar");

    document.querySelectorAll("[data-mm-compare]").forEach(function (input) {
      input.checked = items.indexOf(input.getAttribute("data-mm-compare")) !== -1;
      input.disabled = !input.checked && items.length >= COMPARE_LIMIT;
    });

    if (!bar) return;
    bar.hidden = items.length === 0;

    var counter = bar.querySelector("[data-mm-compare-count]");
    if (counter) counter.textContent = String(items.length);

    var link = bar.querySelector("[data-mm-compare-link]");
    if (link) {
      var base = link.getAttribute("href").split("?")[0];
      link.setAttribute("href", base + "?" + items.map(function (slug) {
        return "m=" + encodeURIComponent(slug);
      }).join("&"));
    }
  }

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.matches || !input.matches("[data-mm-compare]")) return;

    var slug = input.getAttribute("data-mm-compare");
    var items = readCompare();
    var position = items.indexOf(slug);

    if (input.checked && position === -1) {
      if (items.length >= COMPARE_LIMIT) {
        input.checked = false;
        return;
      }
      items.push(slug);
    } else if (!input.checked && position !== -1) {
      items.splice(position, 1);
    }
    writeCompare(items);
  });

  document.addEventListener("click", function (event) {
    var remove = event.target.closest("[data-mm-compare-remove]");
    if (remove) {
      var slug = remove.getAttribute("data-mm-compare-remove");
      var items = readCompare().filter(function (item) { return item !== slug; });
      writeCompare(items);
      // Таблица строится на сервере, поэтому её нужно перезапросить.
      var next = items.length
        ? window.location.pathname + "?" + items.map(function (value) {
            return "m=" + encodeURIComponent(value);
          }).join("&")
        : window.location.pathname;
      window.location.href = next;
      return;
    }

    if (event.target.closest("[data-mm-compare-clear]")) {
      writeCompare([]);
      if (window.location.pathname.indexOf("/sravnenie/") !== -1) {
        window.location.href = window.location.pathname;
      }
    }
  });

  // Список каталога подменяется HTMX, поэтому состояние галочек
  // восстанавливается после каждой замены.
  document.addEventListener("htmx:afterSwap", renderCompare);
  document.addEventListener("DOMContentLoaded", renderCompare);

  // Маска телефона: +7 (999) 999-99-99.
  //
  // Обработчик навешен на документ, а не на конкретные поля: формы заявок
  // приезжают через HTMX уже после загрузки страницы, и привязка к элементам
  // при старте их бы не покрыла.
  document.addEventListener("input", function (event) {
    var field = event.target;
    if (!field.matches || !field.matches('input[type="tel"]')) return;

    var deleting = event.inputType && event.inputType.indexOf("delete") === 0;
    var formatted = formatPhone(field.value);

    // Если при удалении маска вернула символ обратно (пользователь стёр скобку
    // или дефис), поле бы «залипло»: нажатие Backspace не меняло бы ничего.
    // В этом случае убираем ещё и цифру перед разделителем.
    if (deleting && formatted.length > field.value.length) {
      formatted = formatPhone(field.value.replace(/\d(?=\D*$)/, ""));
    }

    field.value = formatted;
    // Курсор ставится в конец: пользователь набирает номер слева направо,
    // а попытки сохранить позицию внутри маски дают больше сбоев, чем пользы.
    var end = field.value.length;
    if (field.setSelectionRange) field.setSelectionRange(end, end);
  });

  function formatPhone(raw) {
    var digits = String(raw).replace(/\D/g, "");
    if (!digits) return "";

    // Номер могли ввести как 8..., +7... или сразу с кода города.
    if (digits[0] === "8" || digits[0] === "7") digits = digits.slice(1);
    digits = digits.slice(0, 10);

    var result = "+7";
    if (digits.length > 0) result += " (" + digits.slice(0, 3);
    if (digits.length >= 3) result += ")";
    if (digits.length > 3) result += " " + digits.slice(3, 6);
    if (digits.length > 6) result += "-" + digits.slice(6, 8);
    if (digits.length > 8) result += "-" + digits.slice(8, 10);
    return result;
  }

  // Мобильное меню: показывает навигацию, скрытую container query.
  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-mm-menu-toggle]")) return;
    var nav = document.querySelector(".mm-nav");
    if (!nav) return;
    var shown = nav.style.display === "flex";
    nav.style.display = shown ? "" : "flex";
    nav.style.flexDirection = "column";
    nav.style.position = "absolute";
    nav.style.top = "64px";
    nav.style.left = "0";
    nav.style.right = "0";
    nav.style.background = "#fff";
    nav.style.padding = "16px";
    nav.style.borderBottom = "3px solid #16181C";
  });
})();

/*
 * Видимый ответ на сбой запроса.
 *
 * htmx по умолчанию не подставляет ответы с кодом 4xx и 5xx: при ошибке
 * сервера страница просто ничего не делала, и человек видел молчащую кнопку.
 * Единственным следом была вкладка «Сеть» в инструментах разработчика.
 */
(function () {
  "use strict";

  var MESSAGE_CLASS = "mm-request-error";

  function showError(event, text) {
    var source = event.detail && event.detail.elt;
    if (!source) {
      return;
    }

    /* Сообщение кладётся рядом с тем, что запрос вызвало: в модальном окне
       заявки, под кнопкой калькулятора — там, куда человек смотрит. */
    var holder = source.closest("form") || source;
    var existing = holder.querySelector("." + MESSAGE_CLASS);
    if (!existing) {
      existing = document.createElement("div");
      existing.className = "mm-form__errors " + MESSAGE_CLASS;
      existing.setAttribute("role", "alert");
      holder.appendChild(existing);
    }
    existing.textContent = text;
  }

  document.addEventListener("htmx:responseError", function (event) {
    var status = event.detail && event.detail.xhr && event.detail.xhr.status;
    if (status === 413) {
      showError(event, "Файл слишком большой. Приложите файл до 10 МБ.");
    } else {
      showError(
        event,
        "Не удалось отправить — попробуйте ещё раз или позвоните нам."
      );
    }
  });

  document.addEventListener("htmx:sendError", function (event) {
    showError(event, "Нет связи с сервером. Проверьте подключение.");
  });

  /* Успешный ответ снимает прежнее сообщение. */
  document.addEventListener("htmx:afterSwap", function () {
    var stale = document.querySelectorAll("." + MESSAGE_CLASS);
    for (var i = 0; i < stale.length; i++) {
      stale[i].remove();
    }
  });
})();
