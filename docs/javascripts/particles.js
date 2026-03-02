// Gold particle system — floating flakes behind the hero image
(function () {
  const hero = document.querySelector('.hero');
  if (!hero) return;

  // Mark body + html for homepage-specific CSS (hide footer, lock scroll)
  document.documentElement.classList.add('hero-page');
  document.body.classList.add('hero-page');

  const canvas = document.createElement('canvas');
  canvas.classList.add('hero-particles');
  hero.insertBefore(canvas, hero.firstChild);

  const ctx = canvas.getContext('2d');
  let particles = [];
  let animId;

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
    // Scale lifetime to canvas height so particles can traverse the full viewport
    const avgSpeed = 0.35; // midpoint of speedY range (0.1–0.6)
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
      p.life = Math.random() * p.maxLife; // stagger initial states
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

      // Flicker effect
      const flicker = Math.sin(p.life * p.flickerSpeed + p.flickerPhase);
      const currentOpacity = p.opacity * (0.5 + 0.5 * flicker);

      // Fade in/out at lifecycle boundaries
      let lifeFade = 1;
      if (p.life < 30) lifeFade = p.life / 30;
      if (p.life > p.maxLife - 30) lifeFade = (p.maxLife - p.life) / 30;

      ctx.globalAlpha = currentOpacity * Math.max(0, lifeFade);
      ctx.fillStyle = p.color;

      // Draw as a soft glowing dot
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();

      // Add a subtle glow
      if (p.size > 1.5) {
        ctx.globalAlpha = currentOpacity * lifeFade * 0.3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // Respawn when dead or off-screen
      if (p.life > p.maxLife || p.y < -10 || p.x < -10 || p.x > canvas.width + 10) {
        particles[i] = createParticle();
        particles[i].y = canvas.height + 5; // respawn from bottom
      }
    }

    ctx.globalAlpha = 1;
    animId = requestAnimationFrame(draw);
  }

  // Pause when not visible
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      if (!animId) draw();
    } else {
      cancelAnimationFrame(animId);
      animId = null;
    }
  });

  window.addEventListener('resize', () => { resize(); init(); });
  init();
  observer.observe(hero);
  draw();
})();
