// Right-click selected Tamil text -> open the tester with it.

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "kuralcheck-test-selection",
    title: "Test “%s” with KuralCheck",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "kuralcheck-test-selection" || !info.selectionText) return;
  const lines = info.selectionText
    .split(/[\n.!?।]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 10);
  await chrome.storage.local.set({ pendingText: lines.join("\n") });
  await chrome.tabs.create({ url: chrome.runtime.getURL("app.html#text") });
});
