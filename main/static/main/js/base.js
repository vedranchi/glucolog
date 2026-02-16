document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".message").forEach((message) => {
    message.addEventListener("click", () => message.remove());
  });
});
