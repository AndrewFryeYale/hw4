// Lets any page open the chat widget without prop drilling (e.g. "Ask our assistant about this item").
export const OPEN_CHAT_EVENT = 'cc:open-chat'

export const openChat = () => window.dispatchEvent(new CustomEvent(OPEN_CHAT_EVENT))
