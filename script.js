// Initialiser Swiper avec effet fade
const swiper = new Swiper(".swiper", {
  loop: true,
  effect: "fade",
  fadeEffect: {
    crossFade: true
  },
  autoplay: {
    delay: 5000,
    disableOnInteraction: false,
  },
});

// === BULLET DOT NAVIGATION ===
const sections = document.querySelectorAll("header, #portfolio, #contact");
const dotLinks = document.querySelectorAll(".dot-nav .dot");

window.addEventListener("scroll", () => {
  let currentIndex = 0;
  sections.forEach((section, index) => {
    if (window.scrollY >= section.offsetTop - window.innerHeight / 2) {
      currentIndex = index;
    }
  });
  dotLinks.forEach((dot) => dot.classList.remove("active"));
  dotLinks[currentIndex].classList.add("active");
});

// === NAVIGATION HORIZONTALE À PROPOS ===
const navHome = document.getElementById("nav-home");
const navAbout = document.getElementById("nav-about");
const aboutSection = document.getElementById("about-section");

// Appliquer le style de base pour que la section À propos soit hors écran
aboutSection.style.position = "fixed";
aboutSection.style.top = "0";
aboutSection.style.left = "100vw";
aboutSection.style.width = "100vw";
aboutSection.style.height = "100vh";
aboutSection.style.zIndex = "1001";
aboutSection.style.transition = "left 0.8s ease";

// Cliquer sur "À propos" → slide in
navAbout.addEventListener("click", (e) => {
  e.preventDefault();
  aboutSection.style.left = "0";
  navHome.classList.remove("active");
  navAbout.classList.add("active");
});

// Cliquer sur "Home" → slide out
navHome.addEventListener("click", (e) => {
  e.preventDefault();
  aboutSection.style.left = "100vw";
  navAbout.classList.remove("active");
  navHome.classList.add("active");
});
