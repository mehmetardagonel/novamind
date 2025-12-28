const FORCE_MAILBOX_LOADING_KEY = "nm_force_mailbox_loading";

export const setForceMailboxLoading = () => {
  sessionStorage.setItem(FORCE_MAILBOX_LOADING_KEY, "1");
};

export const shouldForceMailboxLoading = () =>
  sessionStorage.getItem(FORCE_MAILBOX_LOADING_KEY) === "1";

export const clearForceMailboxLoading = () => {
  sessionStorage.removeItem(FORCE_MAILBOX_LOADING_KEY);
};
