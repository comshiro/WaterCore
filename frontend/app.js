const output = document.getElementById("output");
const button = document.getElementById("load-demo");

button.addEventListener("click", async () => {
  output.textContent = "Loading...";

  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/risk/demo");
    const data = await response.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    output.textContent = `Request failed: ${error}`;
  }
});
