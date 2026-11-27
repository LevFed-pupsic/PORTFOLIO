"use strict";
document.documentElement.classList.add("js");
// Мобильное меню: состояние ARIA, Escape и возврат фокуса.
const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#navigation");

function closeMenu(returnFocus = false) {
  menuButton.setAttribute("aria-expanded", "false");
  navigation.classList.remove("open");
  menuButton.setAttribute("aria-label", "Открыть меню");
  if (returnFocus) menuButton.focus();
}
menuButton.addEventListener("click", () => {
  const open = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(open));
  navigation.classList.toggle("open", open);
  menuButton.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
});
navigation
  .querySelectorAll("a")
  .forEach((link) => link.addEventListener("click", () => closeMenu()));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true")
    closeMenu(true);
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".header")) closeMenu();
});
navigation.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeMenu(true);
});
window
  .matchMedia("(min-width: 701px)")
  .addEventListener("change", () => closeMenu());
// Фильтры сохраняют доступность: скрытые работы исключены из Tab-порядка.
document.querySelectorAll("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    const gallery = document.querySelector(".gallery");
    document
      .querySelectorAll("[data-filter]")
      .forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)),
      );
    gallery.classList.remove("is-changing");
    gallery.classList.toggle("is-filtered", button.dataset.filter !== "all");
    let count = 0;
    gallery.querySelectorAll(".work").forEach((work) => {
      work.hidden =
        button.dataset.filter !== "all" &&
        work.dataset.category !== button.dataset.filter;
      if (!work.hidden) {
        count++;
        work.classList.add("visible");
      }
    });
    document.querySelector(".gallery-count").textContent =
      `${count} ${count === 1 ? "кадр" : count < 5 ? "кадра" : "кадров"}`;
    void gallery.offsetWidth;
    gallery.classList.add("is-changing");
  }),
);
// Нативный dialog удерживает фокус; полноэкранная галерея работает с клавиатуры.
const dialog = document.querySelector(".lightbox");
const fullImage = dialog.querySelector(".lightbox-image");
const caption = dialog.querySelector(".lightbox-caption");
let photos = [],
  current = 0,
  opener = null;

function showPhoto(index) {
  current = (index + photos.length) % photos.length;
  const photo = photos[current];
  fullImage.classList.remove("changing");
  fullImage.src = photo.dataset.full;
  void fullImage.offsetWidth;
  fullImage.classList.add("changing");
  fullImage.alt = photo.querySelector("img").alt;
  caption.textContent = `${photo.dataset.caption} · ${current + 1} / ${photos.length}`;
}
document.querySelectorAll("[data-full]").forEach((button) =>
  button.addEventListener("click", () => {
    photos = [...document.querySelectorAll("[data-full]")].filter(
      (item) => !item.closest(".work").hidden,
    );
    opener = button;
    showPhoto(photos.indexOf(button));
    dialog.showModal();
    document.body.classList.add("locked");
  }),
);
dialog
  .querySelector(".lightbox-close")
  .addEventListener("click", () => dialog.close());
dialog
  .querySelector(".lightbox-prev")
  .addEventListener("click", () => showPhoto(current - 1));
dialog
  .querySelector(".lightbox-next")
  .addEventListener("click", () => showPhoto(current + 1));
dialog.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    const controls = [...dialog.querySelectorAll("button:not([disabled])")];
    const first = controls[0], last = controls[controls.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }

  if (e.key === "ArrowRight") {
    e.preventDefault();
    showPhoto(current + 1);
  }
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    showPhoto(current - 1);
  }
});
dialog.addEventListener("close", () => {
  document.body.classList.remove("locked");
  opener?.focus();
});
let touchX = null;
fullImage.addEventListener(
  "touchstart",
  (e) => {
    touchX = e.changedTouches[0].clientX;
  },
  {
    passive: true,
  },
);
fullImage.addEventListener(
  "touchend",
  (e) => {
    const delta = e.changedTouches[0].clientX - touchX;
    if (touchX !== null && Math.abs(delta) > 60)
      showPhoto(current + (delta < 0 ? 1 : -1));
    touchX = null;
  },
  {
    passive: true,
  },
);
// Сервис выбирается из строки прайса; пользователь может изменить выбор.
document.querySelectorAll("[data-service]").forEach((link) =>
  link.addEventListener("click", () => {
    document.querySelector("#service").value = link.dataset.service;
  }),
);
const form = document.querySelector("#contact-form");
if (form)
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector("[type=submit]");
    if (button.disabled) return;
    const status = document.querySelector("#form-status");
    const data = Object.fromEntries(new FormData(form));
    data.consent = form.elements.consent.checked;
    button.disabled = true;
    button.textContent = "Сохраняем…";
    status.classList.remove("error");
    status.textContent = "Отправляем вашу заявку…";
    form.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/api/inquiries", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        signal: controller.signal,
      });
      const result = await response.json();
      status.textContent =
        result.message || "Не удалось обработать ответ. Попробуйте позже.";
      status.classList.toggle("error", !response.ok);
      if (response.ok) form.reset();
    } catch (error) {
      status.classList.add("error");
      status.textContent =
        "Связь прервалась. Данные остались в форме — попробуйте ещё раз.";
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      button.textContent = "Отправить заявку";
      form.removeAttribute("aria-busy");
    }
  });
