/*
 * Отправка целей в Яндекс.Метрику.
 *
 * Подключается только когда счётчик показывается — файл включён в партиал
 * счётчика, а не в base.html.
 *
 * Цели по заявкам не вешаются на клик по кнопке: клик не означает заявку,
 * форма может не пройти проверку, а повторная отправка склеивается с прежней.
 * Поэтому сервер кладёт в ответ маркер `data-mm-goal-reached` — и только тогда,
 * когда заявка действительно создана.
 *
 * Атрибуты намеренно разные. `data-mm-goal-reached` означает «цель уже
 * достигнута, отправить сейчас», `data-mm-goal` — «отправить, если по этому
 * кликнут». Общий атрибут приводил бы к тому, что размеченная ссылка на
 * мессенджер засчитывалась бы целью при каждом открытии страницы.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  /* Число, а не строка: `init` счётчика вызывается с числом, и цель должна
     уйти на тот же идентификатор. */
  var counterId = Number(script && script.dataset.mmMetrikaId) || 0;
  if (!counterId) {
    return;
  }

  /* Счётчик режет блокировщик у заметной доли посетителей. Без проверки каждый
     клик по телефону давал бы исключение в консоли. */
  function reach(goal) {
    if (typeof window.ym === "function") {
      window.ym(counterId, "reachGoal", goal);
    }
  }

  var REACHED = "[data-mm-goal-reached]";

  /* Сам подменённый узел тоже может быть маркером: при `hx-swap="outerHTML"`
     корнями ответа становятся его элементы верхнего уровня, а
     `querySelectorAll` ищет только среди потомков и такой маркер пропустит. */
  function collectMarkers(root) {
    var found = root.querySelectorAll ? [].slice.call(root.querySelectorAll(REACHED)) : [];
    if (root.matches && root.matches(REACHED)) {
      found.unshift(root);
    }
    return found;
  }

  /* Один и тот же маркер не должен сработать дважды: при обычной отправке
     формы он приходит подменой блока, а без JavaScript-навигации — уже внутри
     целой страницы. */
  function sendReachedGoals(root) {
    var markers = collectMarkers(root || document);
    for (var i = 0; i < markers.length; i++) {
      var marker = markers[i];
      if (marker.dataset.mmGoalSent) {
        continue;
      }
      marker.dataset.mmGoalSent = "1";
      reach(marker.dataset.mmGoalReached);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    sendReachedGoals(document);
  });

  /* Слушатель вешается на документ, а не на body: файл подключён из <head>
     с `defer`, и body к этому моменту ещё может не существовать. */
  document.addEventListener("htmx:afterSwap", function (event) {
    sendReachedGoals(event.target);
  });

  /* Клики по контактам. Телефон и почта ловятся по адресу — это стабильно.
     Мессенджеры размечены в шаблоне: ссылка берётся из настроек сайта, и
     менеджер вправе вписать туда короткий адрес или api.whatsapp.com, из-за
     чего селектор по «wa.me» молча перестал бы работать. */
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link) {
      return;
    }

    var marked = link.closest("[data-mm-goal]") || link;
    if (marked.dataset && marked.dataset.mmGoal) {
      reach(marked.dataset.mmGoal);
      return;
    }

    var href = link.getAttribute("href") || "";
    if (href.indexOf("tel:") === 0) {
      reach("click_phone");
    } else if (href.indexOf("mailto:") === 0) {
      reach("click_email");
    }
  });
})();
