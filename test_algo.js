const state = {
  items: [
    { id: 'random1', type: 'userSaid', text: 'Bro lets get back to the work what all we have today' },
    { id: 'asst_turn1', type: 'surfacing', text: 'Your workspace...' }
  ],
  activeStreamId: null
};

const newItems = [
  { id: 'turn1', type: 'userSaid', text: 'Bro lets get back to the work what all we have today' },
  { id: 'asst_turn1', type: 'surfacing', text: 'Your workspace...' }
];

// 1. Strictly deduplicate newItems by ID, keeping the latest occurrence
const uniqueNewItems = [];
const seenIds = new Set();
for (let i = newItems.length - 1; i >= 0; i--) {
  if (!seenIds.has(newItems[i].id)) {
    seenIds.add(newItems[i].id);
    uniqueNewItems.unshift(newItems[i]);
  }
}

// 2. Also deduplicate consecutive identical user messages in newItems
const finalNewItems = [];
let lastUserText = '';
for (const item of uniqueNewItems) {
  if (item.type === 'userSaid') {
    if (item.text === lastUserText) {
      continue; // Skip consecutive duplicate user messages
    }
    lastUserText = item.text;
  } else {
    lastUserText = ''; // reset on non-user message
  }
  finalNewItems.push(item);
}

// 3. Keep any in-flight active streams that weren't in the new list
const finalNewIds = new Set(finalNewItems.map(i => i.id));
const activeUnsaved = state.items.filter(i => 
  !finalNewIds.has(i.id) && 
  i.type !== 'userSaid' && 
  (i.type !== 'surfacing' || i.id === state.activeStreamId)
);

const finalItems = [...finalNewItems, ...activeUnsaved];
console.log(JSON.stringify(finalItems, null, 2));
