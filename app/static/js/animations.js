"use strict";
// CSS и IntersectionObserver достаточно: внешняя анимационная библиотека не нужна.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let observer;

function configureMotion() {
    observer?.disconnect();
    document.documentElement.classList.toggle('motion', !reducedMotion.matches);
    if (reducedMotion.matches || !('IntersectionObserver' in window)) {
        document.documentElement.classList.remove('motion');
        return;
    }
    observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.08
    });
    document.querySelectorAll('.reveal').forEach(element => observer.observe(element));
}
configureMotion();
reducedMotion.addEventListener('change', configureMotion);
// Параллакс ограничен 16px, работает только на первом экране и на широком экране.
const heroImage = document.querySelector('.hero-photo img');
let scheduled = false;

function updateParallax() {
    scheduled = false;
    if (!heroImage) return;
    if (reducedMotion.matches || window.innerWidth < 701) {
        heroImage.style.transform = '';
        return;
    }
    if (window.scrollY < window.innerHeight) heroImage.style.transform = `translateY(${Math.min(window.scrollY * .025, 16)}px) scale(1.04)`;
}
window.addEventListener('scroll', () => {
    if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(updateParallax);
    }
}, {
    passive: true
});
reducedMotion.addEventListener('change', updateParallax);
window.addEventListener('resize', updateParallax);
