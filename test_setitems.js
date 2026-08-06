const state = {
    items: [
        { id: "opt_1", type: "userSaid", text: "sup" },
        { id: "asst_1", type: "surfacing", paragraphs: ["You're back..."] }
    ]
};

const newItems = [
    { id: "turn_1", type: "userSaid", text: "sup" },
    { id: "asst_1", type: "surfacing", paragraphs: ["You're back..."] },
    { id: "turn_2", type: "userSaid", text: "hello" },
    { id: "asst_2", type: "surfacing", paragraphs: ["How can I help?"] }
];

const newIds = new Set(newItems.map(i => i.id));
const activeUnsaved = state.items.filter(i => !newIds.has(i.id) && i.type !== 'userSaid');
const items = [...newItems, ...activeUnsaved];

console.log(JSON.stringify(items, null, 2));
