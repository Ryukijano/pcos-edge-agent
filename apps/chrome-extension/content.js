// PCOS Content Script — captures page context and selection
// Runs on all pages, listens for context requests from the extension

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'pcos-capture-context') {
    sendResponse({
      url: window.location.href,
      page_title: document.title,
      selection: window.getSelection().toString(),
      dom_summary: document.body?.innerText?.slice(0, 500) || '',
      tab_group: document.title, // simplified
    });
    return true;
  }
});
