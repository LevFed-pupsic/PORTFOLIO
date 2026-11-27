"use strict";
// Progressive enhancement: observers never hide content before it enters the view.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
let observer;
function configureMotion() {
  observer?.disconnect();
  document.documentElement.classList.toggle("motion", !reducedMotion.matches);
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08 },
  );
  document
    .querySelectorAll(".reveal:not(.visible)")
    .forEach((element) => observer.observe(element));
}
configureMotion();
reducedMotion.addEventListener("change", configureMotion);
const heroImage = document.querySelector(".hero-photo img");
const progress = document.querySelector(".scroll-progress");
let scheduled = false;
function updateScroll() {
  scheduled = false;
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.transform = `scaleX(${max > 0 ? Math.min(window.scrollY / max, 1) : 0})`;
  if (!heroImage) return;
  if (
    reducedMotion.matches ||
    !finePointer.matches ||
    window.innerWidth < 701
  ) {
    heroImage.style.transform = "";
    return;
  }
  if (window.scrollY < window.innerHeight)
    heroImage.style.transform = `translateY(${Math.min(window.scrollY * 0.018, 10)}px) scale(1.04)`;
}
window.addEventListener(
  "scroll",
  () => {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(updateScroll);
    }
  },
  { passive: true },
);
reducedMotion.addEventListener("change", updateScroll);
finePointer.addEventListener("change", updateScroll);
window.addEventListener("resize", updateScroll);
updateScroll();
