const dialogs = Array.from(document.querySelectorAll("dialog"));
const showButtons = Array.from(document.querySelectorAll("button[data-dialog-open]"));
const closeButtons = Array.from(document.querySelectorAll("button[data-dialog-close]"));
dialogs.forEach((dialog, index) => {
	const showButton = showButtons[index];
	const closeButton = closeButtons[index];

	showButton.addEventListener("click", () => {
		dialog.showModal();
	});

	closeButton.addEventListener("click", () => {
		dialog.close();
	});
});