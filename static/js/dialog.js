const dialogs = Array.from(document.querySelectorAll("dialog"));
const showButtons = Array.from(document.querySelectorAll("button[data-dialog-open]"));
const closeButtons = Array.from(document.querySelectorAll("[data-dialog-close]"));
console.log(closeButtons);

dialogs.forEach((dialog, index) => {
    const showButton = showButtons[index];
    const closeButton = closeButtons[index];

    showButton.addEventListener("click", () => {
        dialog.showModal();
    });

    closeButton.addEventListener("click", () => {
        dialog.close();
    });

    const cancelButton = dialog.querySelector("button[type='button'][data-dialog-close]");
    if (cancelButton) {
        cancelButton.addEventListener("click", () => {
            dialog.close();
        });
    }

    const form = dialog.querySelector("form");
    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault(); // Prevent form submission
            const formData = new FormData(form);
            let url = form.getAttribute("action");
            console.log(url);
            if (!url) {
                url = window.location.href;
            }
            const method = form.getAttribute("method");

            fetch(url, {
                method: method,
                body: formData
            })
            .then(response => {
                // Handle response
                if (response.ok) {
                    // Optionally close the dialog after successful form submission
                    dialog.close();
                    window.location.reload();
                } else {
                    // Handle errors
                    console.error('Form submission failed');
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    }
});
