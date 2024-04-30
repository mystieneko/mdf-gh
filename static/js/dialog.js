const dialogs = Array.from(document.querySelectorAll("dialog"));
const showButtons = Array.from(document.querySelectorAll("[data-dialog-open]"));

dialogs.forEach((dialog, index) => {
    const showButton = showButtons[index];
    const closeButtons = Array.from(dialog.querySelectorAll("[data-dialog-close]")); // Select all close buttons within the dialog

    showButton.addEventListener("click", () => {
        dialog.showModal();
    });

    closeButtons.forEach(closeButton => { // Iterate over each closeButton
        closeButton.addEventListener("click", () => {
            dialog.close();
        });
    });
});
