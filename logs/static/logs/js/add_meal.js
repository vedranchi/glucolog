document.addEventListener("DOMContentLoaded", () => {
  const carbsInput = document.getElementById("carbs");
  const proteinInput = document.getElementById("protein");
  const fatsInput = document.getElementById("fats");
  const caloriesInput = document.getElementById("calories");

  if (!carbsInput || !proteinInput || !fatsInput || !caloriesInput) {
    return;
  }

  const calculateCalories = () => {
    const carbs = parseFloat(carbsInput.value) || 0;
    const protein = parseFloat(proteinInput.value) || 0;
    const fats = parseFloat(fatsInput.value) || 0;
    const calories = carbs * 4 + protein * 4 + fats * 9;
    caloriesInput.value = Math.round(calories);
  };

  carbsInput.addEventListener("input", calculateCalories);
  proteinInput.addEventListener("input", calculateCalories);
  fatsInput.addEventListener("input", calculateCalories);

  // Only derive calories on load if there is actually something to derive them
  // from. The macro fields are nullable, so editing a meal that stored calories
  // but no macros arrives here with all three blank — recomputing would put 0
  // in the readonly field and overwrite the saved value on save.
  const hasMacros = [carbsInput, proteinInput, fatsInput].some(
    (input) => input.value.trim() !== ""
  );
  if (hasMacros) {
    calculateCalories();
  }
});
