// Gold particle system — floating flakes behind the hero image.
// Re-entrant so MkDocs Material instant navigation can rebind cleanly.
(function () {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Signal to CSS that JS is running so progressive-enhancement rules can apply.
  document.documentElement.classList.add('js-ready');

  let teardown = null;

  function initHero() {
    if (teardown) { teardown(); teardown = null; }

    const hero = document.querySelector('.hero');
    if (!hero) {
      // Not the landing page — strip any lingering hero-page styling from a prior nav.
      document.documentElement.classList.remove('hero-page');
      document.body.classList.remove('hero-page');
      return;
    }

    document.documentElement.classList.add('hero-page');
    document.body.classList.add('hero-page');

    const sections = document.querySelectorAll('.landing-section');
    let revealObserver = null;
    if (sections.length) {
      if (prefersReducedMotion) {
        sections.forEach(s => s.classList.add('visible'));
      } else {
        revealObserver = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add('visible');
              revealObserver.unobserve(entry.target);
            }
          });
        }, { threshold: 0.12 });
        sections.forEach(s => revealObserver.observe(s));
      }
    }

    if (prefersReducedMotion) {
      teardown = () => {
        if (revealObserver) revealObserver.disconnect();
      };
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.classList.add('hero-particles');
    hero.insertBefore(canvas, hero.firstChild);

    const ctx = canvas.getContext('2d');
    let particles = [];
    let animId = null;

    const GOLD_COLORS = [
      'rgba(212, 175, 55, 0.8)',
      'rgba(241, 210, 161, 0.6)',
      'rgba(207, 153, 95, 0.7)',
      'rgba(226, 176, 126, 0.5)',
      'rgba(138, 102, 35, 0.4)',
    ];

    function resize() {
      canvas.width = hero.offsetWidth;
      canvas.height = hero.offsetHeight;
    }

    function createParticle() {
      const avgSpeed = 0.35;
      const baseLife = Math.ceil(canvas.height / avgSpeed);
      return {
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 3 + 0.5,
        speedX: (Math.random() - 0.5) * 0.3,
        speedY: -Math.random() * 0.5 - 0.1,
        color: GOLD_COLORS[Math.floor(Math.random() * GOLD_COLORS.length)],
        opacity: Math.random() * 0.8 + 0.2,
        flickerSpeed: Math.random() * 0.02 + 0.005,
        flickerPhase: Math.random() * Math.PI * 2,
        life: 0,
        maxLife: Math.random() * baseLife + baseLife * 0.5,
      };
    }

    function init() {
      resize();
      particles = [];
      const count = Math.floor((canvas.width * canvas.height) / 8000);
      for (let i = 0; i < count; i++) {
        const p = createParticle();
        p.life = Math.random() * p.maxLife;
        particles.push(p);
      }
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.speedX;
        p.y += p.speedY;
        p.life++;
        const flicker = Math.sin(p.life * p.flickerSpeed + p.flickerPhase);
        const currentOpacity = p.opacity * (0.5 + 0.5 * flicker);
        let lifeFade = 1;
        if (p.life < 30) lifeFade = p.life / 30;
        if (p.life > p.maxLife - 30) lifeFade = (p.maxLife - p.life) / 30;
        ctx.globalAlpha = currentOpacity * Math.max(0, lifeFade);
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        if (p.size > 1.5) {
          ctx.globalAlpha = currentOpacity * lifeFade * 0.3;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
          ctx.fill();
        }
        if (p.life > p.maxLife || p.y < -10 || p.x < -10 || p.x > canvas.width + 10) {
          particles[i] = createParticle();
          particles[i].y = canvas.height + 5;
        }
      }
      ctx.globalAlpha = 1;
      animId = requestAnimationFrame(draw);
    }

    const visibilityObserver = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        if (!animId) draw();
      } else {
        cancelAnimationFrame(animId);
        animId = null;
      }
    });

    const onResize = () => { resize(); init(); };
    window.addEventListener('resize', onResize);
    init();
    visibilityObserver.observe(hero);
    draw();

    teardown = () => {
      cancelAnimationFrame(animId);
      animId = null;
      visibilityObserver.disconnect();
      if (revealObserver) revealObserver.disconnect();
      window.removeEventListener('resize', onResize);
      canvas.remove();
    };
  }

  if (typeof document$ !== 'undefined') {
    document$.subscribe(initHero);
  } else {
    document.addEventListener('DOMContentLoaded', initHero);
  }
})();

// Avatar lightbox — click any .specialist-avatar or .research-poster to view full-size
(function () {
  let overlay = null;

  function openLightbox(src, alt, variant) {
    overlay = document.createElement('div');
    overlay.className = 'avatar-lightbox';
    if (variant) overlay.classList.add('avatar-lightbox--' + variant);
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', alt || 'Image');

    const img = document.createElement('img');
    img.className = 'avatar-lightbox__img';
    img.src = src;
    img.alt = alt || '';
    overlay.appendChild(img);

    overlay.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', onKeyDown);
    document.body.appendChild(overlay);

    requestAnimationFrame(() => requestAnimationFrame(() => {
      overlay.classList.add('avatar-lightbox--visible');
    }));

    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    if (!overlay) return;
    overlay.classList.remove('avatar-lightbox--visible');
    const el = overlay;
    overlay = null;
    document.removeEventListener('keydown', onKeyDown);
    document.body.style.overflow = '';
    setTimeout(() => el.remove(), 280);
  }

  function onKeyDown(e) {
    if (e.key === 'Escape') closeLightbox();
  }

  function init() {
    document.querySelectorAll('.specialist-avatar, .research-poster').forEach(img => {
      if (img.dataset.lightboxBound) return;
      img.dataset.lightboxBound = '1';
      const variant = img.classList.contains('research-poster') ? 'poster' : null;
      img.addEventListener('click', () => openLightbox(img.src, img.alt, variant));
    });
  }

  if (typeof document$ !== 'undefined') {
    document$.subscribe(init);
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
