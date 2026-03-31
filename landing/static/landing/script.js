const menuBtn = document.getElementById("menuBtn");
const menu = document.getElementById("menu");

if (menuBtn && menu) {
  menuBtn.addEventListener("click", () => {
    const isOpen = menu.classList.toggle("open");
    menuBtn.setAttribute("aria-expanded", String(isOpen));
  });

  menu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      menu.classList.remove("open");
      menuBtn.setAttribute("aria-expanded", "false");
    });
  });
}

const revealItems = document.querySelectorAll(".reveal");
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("show");
      }
    });
  },
  { threshold: 0.15 }
);
revealItems.forEach((item) => observer.observe(item));

const modal = document.getElementById("detailModal");
const openButtons = document.querySelectorAll("[data-open-details]");
const closeButtons = document.querySelectorAll("[data-close-details]");
const slides = Array.from(document.querySelectorAll(".detail-slide"));
const detailTitle = document.getElementById("detailTitle");
const detailCounter = document.getElementById("detailCounter");
const prevBtn = document.getElementById("detailPrev");
const nextBtn = document.getElementById("detailNext");

const slideOrder = ["overview", "features", "workflow", "technical"];
let currentIndex = 0;

function setSlide(index) {
  currentIndex = index;
  const key = slideOrder[currentIndex];

  slides.forEach((slide) => {
    slide.classList.toggle("active", slide.dataset.slide === key);
  });

  const activeSlide = slides.find((slide) => slide.dataset.slide === key);
  const heading = activeSlide?.querySelector("h4")?.textContent || "Details";

  detailTitle.textContent = heading;
  detailCounter.textContent = `${currentIndex + 1} / ${slideOrder.length}`;
  prevBtn.disabled = currentIndex === 0;
  nextBtn.disabled = currentIndex === slideOrder.length - 1;
}

function openModal(startKey) {
  const foundIndex = slideOrder.indexOf(startKey);
  setSlide(foundIndex >= 0 ? foundIndex : 0);
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

openButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openModal(button.dataset.openDetails);
  });
});

closeButtons.forEach((button) => {
  button.addEventListener("click", closeModal);
});

prevBtn?.addEventListener("click", () => {
  if (currentIndex > 0) {
    setSlide(currentIndex - 1);
  }
});

nextBtn?.addEventListener("click", () => {
  if (currentIndex < slideOrder.length - 1) {
    setSlide(currentIndex + 1);
  }
});

document.addEventListener("keydown", (event) => {
  if (!modal.classList.contains("open")) {
    return;
  }

  if (event.key === "Escape") {
    closeModal();
  }
  if (event.key === "ArrowLeft" && currentIndex > 0) {
    setSlide(currentIndex - 1);
  }
  if (event.key === "ArrowRight" && currentIndex < slideOrder.length - 1) {
    setSlide(currentIndex + 1);
  }
});
